"""Controller: サブゴール列を順に実行。move_toは解析IKで関節角に変換し JointTrajectory を送る。

CRANE+ V2 の実測値(講義イメージ, Ignition Gazebo, URDF由来):
  joint2(肩)の高さ 0.0714 m, 上腕 0.083 m, 前腕 0.0935 m, joint4→把持点 0.11 m
関節の向き(実測): joint1 正=左旋回(+y側), joint2 正=前傾, joint3/joint4 正=後ろ(鉛直へ戻す向き)
  → 各リンクの鉛直からの前傾角: θ2=q2, θ3=q2-q3, θ4=q2-q3-q4
"""
import json
import math

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

H_SHOULDER = 0.0714  # base_link → joint2 [m]
L_UPPER = 0.083      # joint2 → joint3
L_FORE = 0.0935      # joint3 → joint4
L_TOOL = 0.110       # joint4 → 把持点(指先の少し内側)

ARM_JOINTS = ["crane_plus_joint1", "crane_plus_joint2", "crane_plus_joint3", "crane_plus_joint4"]
GRIPPER_JOINT = ["crane_plus_joint_hand"]
JOINT_LIMITS = [(-2.61, 2.61), (-1.82, 1.78), (-2.55, 2.45), (-1.84, 1.76)]
# グリッパ関節の可動範囲(URDF: 109.38°〜188.27° − 150°)。上限を超える指令を送ると Gazebo 上で関節が上限に張り付いて
# 開かなくなり、Gazebo の再起動が必要になる(実測)。必ずこの範囲に丸める
GRIPPER_LIMITS = (-0.70, 0.66)


def ik(x, y, z, tool_pitch_deg=None):
    """把持点(x,y,z)[ロボットbase_link基準]へ。tool_pitchは鉛直下向きを180°とする前傾角。
    指定が無ければ真下(180°)から 110° まで順に試し、最初に解けた関節角を返す。失敗時 None。"""
    q1 = math.atan2(y, x)
    r = math.hypot(x, y)
    pitches = [tool_pitch_deg] if tool_pitch_deg is not None else [180, 165, 150, 135, 120, 110]
    for pdeg in pitches:
        th4 = math.radians(pdeg)
        # 手首(joint4)の位置
        wr = r - L_TOOL * math.sin(th4)
        wz = z - L_TOOL * math.cos(th4) - H_SHOULDER
        d = math.hypot(wr, wz)
        if d > L_UPPER + L_FORE or d < abs(L_UPPER - L_FORE):
            continue
        cos_e = (d * d - L_UPPER ** 2 - L_FORE ** 2) / (2 * L_UPPER * L_FORE)
        elbow = math.acos(max(-1.0, min(1.0, cos_e)))  # 肘の屈曲(0=伸展)
        # 肘を上(手前に折る)にする解: θ3 = θ2 + elbow
        phi = math.atan2(wr, wz)  # 手首方向の鉛直からの角
        beta = math.atan2(L_FORE * math.sin(elbow), L_UPPER + L_FORE * math.cos(elbow))
        th2 = phi - beta
        th3 = th2 + elbow
        q2, q3, q4 = th2, th2 - th3, th3 - th4
        q = [q1, q2, q3, q4]
        if all(lo <= v <= hi for v, (lo, hi) in zip(q, JOINT_LIMITS)):
            return q
    return None


def fk(q):
    """検証用の順運動学: 把持点の座標を返す。"""
    q1, q2, q3, q4 = q
    th2, th3, th4 = q2, q2 - q3, q2 - q3 - q4
    r = L_UPPER * math.sin(th2) + L_FORE * math.sin(th3) + L_TOOL * math.sin(th4)
    z = H_SHOULDER + L_UPPER * math.cos(th2) + L_FORE * math.cos(th3) + L_TOOL * math.cos(th4)
    return [r * math.cos(q1), r * math.sin(q1), z]


class Controller(Node):
    def __init__(self):
        super().__init__("controller")
        self.declare_parameter("joint_cmd_topic", "/crane_plus_arm_controller/joint_trajectory")
        self.declare_parameter("gripper_cmd_topic", "/crane_plus_gripper_controller/joint_trajectory")
        self.declare_parameter("move_duration_sec", 2.0)   # グリッパ開閉と、関節速度で決めた時間の下限
        self.declare_parameter("joint_speed_rad_s", 0.5)   # 腕の最大関節速度。大きな旋回ほど時間をかけ、把持中の滑落を防ぐ
        self.declare_parameter("max_move_sec", 4.0)
        self.declare_parameter("settle_sec", 0.5)          # 動作完了後に次の指令までおく余裕
        # CRANE+ のグリッパは片側の指だけが動く。閉じると物体は固定指側(+y, 反時計回り側)へ押し付けられ、
        # 物体中心が把持点から接線方向に約 1.2cm ずれる(実測)。把持中は置き位置をその分だけ戻して補正する
        self.declare_parameter("held_tangential_offset_m", 0.012)
        # 遠い置き位置では手先が傾く(最大 30°)。傾いて保持したブロックは離すと外側へ転がるので、
        # 傾き角の正弦に比例して置き位置を手前に寄せる(実測: 30° で約 1.5cm)
        self.declare_parameter("held_radial_gain_m", 0.03)
        self.declare_parameter("gripper_open", -0.5)
        self.declare_parameter("gripper_close", 0.35)
        self.declare_parameter("home_joints", [0.0, 0.0, 0.0, 0.0])
        self.arm_pub = self.create_publisher(JointTrajectory, self.get_parameter("joint_cmd_topic").value, 10)
        self.grip_pub = self.create_publisher(JointTrajectory, self.get_parameter("gripper_cmd_topic").value, 10)
        self.status_pub = self.create_publisher(String, "/controller/status", 10)
        self.create_subscription(String, "/plan/subgoals", self.on_plan, 10)
        self.create_subscription(String, "/controller/abort", self.on_abort, 10)  # monitor が運搬失敗を検知したとき
        self.queue = []
        self.last_q = list(self.get_parameter("home_joints").value)
        self.holding = False
        self.done_pending = False   # 最後のサブゴールの動作完了を待ってから done を出す(カメラ知覚では腕が物体を隠すため)
        self.last_sg = None
        self.busy_until = None   # 現在の動作が終わる時刻(ノードのクロック。use_sim_time ならシミュレーション時刻)
        self.timer = self.create_timer(0.25, self.step)
        self.get_logger().info("controller ready")

    def on_plan(self, msg: String):
        data = json.loads(msg.data)
        if "error" in data:
            self.get_logger().warn(f"plan rejected: {data['error']}")
            self.status_pub.publish(String(data=json.dumps({"state": "rejected", "reason": data["error"]}, ensure_ascii=False)))
            return
        self.queue = list(data["subgoals"])
        self.done_pending = False
        self.get_logger().info(f"queued {len(self.queue)} subgoals")

    def on_abort(self, msg: String):
        """残りの計画を捨て、グリッパを開いて初期姿勢へ戻る(再計画は planner が行う)。"""
        n = len(self.queue)
        self.queue = [{"action": "release", "note": "中止: 開放"}, {"action": "home", "note": "中止: 初期姿勢"}]
        self.done_pending = False
        self.get_logger().warn(f"plan aborted ({msg.data}); dropped {n} subgoals")
        self.status_pub.publish(String(data=json.dumps({"state": "aborted", "reason": msg.data}, ensure_ascii=False)))

    def _now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def _arm_duration(self, q):
        """関節の最大移動量から所要時間を決める(下限 move_duration_sec, 上限 max_move_sec)。"""
        dq = max(abs(a - b) for a, b in zip(q, self.last_q))
        lo = float(self.get_parameter("move_duration_sec").value)
        hi = float(self.get_parameter("max_move_sec").value)
        return min(hi, max(lo, dq / float(self.get_parameter("joint_speed_rad_s").value)))

    def step(self):
        if self.busy_until is not None and self._now() < self.busy_until:
            return
        if self.done_pending:
            self.done_pending = False
            self.status_pub.publish(String(data=json.dumps({"state": "done", "last": self.last_sg}, ensure_ascii=False)))
        if not self.queue:
            return
        sg = self.queue.pop(0)
        act = sg["action"]
        sec = float(self.get_parameter("move_duration_sec").value)
        if act == "move_to":
            q = ik(*sg["target"])
            if q is not None and self.holding:
                x, y, z = sg["target"]
                r = math.hypot(x, y)
                tilt = abs(math.pi - (q[1] - q[2] - q[3]))   # 手先の鉛直からの傾き
                dr = float(self.get_parameter("held_radial_gain_m").value) * math.sin(tilt)
                q2 = ik(x * (r - dr) / r, y * (r - dr) / r, z) if dr > 0 and r > dr else None
                if q2 is not None:
                    q = q2
                q[0] -= float(self.get_parameter("held_tangential_offset_m").value) / max(r, 0.05)
            if q is None:
                self.get_logger().error(f"IK failed for {sg['target']}")
                self.status_pub.publish(String(data=json.dumps({"state": "failed", "reason": f"IK不可: {sg['target']}"}, ensure_ascii=False)))
                self.queue.clear()
                return
            sec = self._arm_duration(q)
            self.get_logger().info(f"move_to {sg['target']} -> q={[round(v, 2) for v in q]} (fk={[round(v, 3) for v in fk(q)]}, {sec:.1f}s)")
            self._send(self.arm_pub, ARM_JOINTS, q, sec)
            self.last_q = q
        elif act == "home":
            q = list(self.get_parameter("home_joints").value)
            sec = self._arm_duration(q)
            self._send(self.arm_pub, ARM_JOINTS, q, sec)
            self.last_q = q
        elif act == "grasp":
            self._send(self.grip_pub, GRIPPER_JOINT, [self._grip(self.get_parameter("gripper_close").value)], sec)
            self.holding = True
        elif act == "release":
            self._send(self.grip_pub, GRIPPER_JOINT, [self._grip(self.get_parameter("gripper_open").value)], sec)
            self.holding = False
        self.done_pending = False   # 最後のサブゴールの動作完了を待ってから done を出す(カメラ知覚では腕が物体を隠すため)
        self.busy_until = self._now() + sec + float(self.get_parameter("settle_sec").value)
        self.last_sg = sg
        if self.queue:
            self.status_pub.publish(String(data=json.dumps({"state": "running", "last": sg}, ensure_ascii=False)))
        elif not str(sg.get("note", "")).startswith("中止"):
            self.done_pending = True   # 動作完了後に done を publish

    @staticmethod
    def _grip(v):
        return min(GRIPPER_LIMITS[1], max(GRIPPER_LIMITS[0], float(v)))

    def _send(self, pub, names, positions, sec):
        msg = JointTrajectory()
        msg.joint_names = names
        pt = JointTrajectoryPoint()
        pt.positions = [float(p) for p in positions]
        pt.time_from_start = Duration(sec=int(sec), nanosec=int((sec % 1) * 1e9))
        msg.points = [pt]
        pub.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(Controller())


if __name__ == "__main__":
    main()
