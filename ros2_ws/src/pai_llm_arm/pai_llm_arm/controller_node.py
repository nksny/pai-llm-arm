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
        self.declare_parameter("move_duration_sec", 2.0)
        self.declare_parameter("gripper_open", -0.5)
        self.declare_parameter("gripper_close", 0.35)
        self.declare_parameter("home_joints", [0.0, 0.0, 0.0, 0.0])
        self.arm_pub = self.create_publisher(JointTrajectory, self.get_parameter("joint_cmd_topic").value, 10)
        self.grip_pub = self.create_publisher(JointTrajectory, self.get_parameter("gripper_cmd_topic").value, 10)
        self.status_pub = self.create_publisher(String, "/controller/status", 10)
        self.create_subscription(String, "/plan/subgoals", self.on_plan, 10)
        self.queue = []
        self.timer = self.create_timer(self.get_parameter("move_duration_sec").value + 0.5, self.step)
        self.get_logger().info("controller ready")

    def on_plan(self, msg: String):
        data = json.loads(msg.data)
        if "error" in data:
            self.get_logger().warn(f"plan rejected: {data['error']}")
            self.status_pub.publish(String(data=json.dumps({"state": "rejected", "reason": data["error"]}, ensure_ascii=False)))
            return
        self.queue = list(data["subgoals"])
        self.get_logger().info(f"queued {len(self.queue)} subgoals")

    def step(self):
        if not self.queue:
            return
        sg = self.queue.pop(0)
        act = sg["action"]
        if act == "move_to":
            q = ik(*sg["target"])
            if q is None:
                self.get_logger().error(f"IK failed for {sg['target']}")
                self.status_pub.publish(String(data=json.dumps({"state": "failed", "reason": f"IK不可: {sg['target']}"}, ensure_ascii=False)))
                self.queue.clear()
                return
            self.get_logger().info(f"move_to {sg['target']} -> q={[round(v, 2) for v in q]} (fk={[round(v, 3) for v in fk(q)]})")
            self._send(self.arm_pub, ARM_JOINTS, q)
        elif act == "home":
            self._send(self.arm_pub, ARM_JOINTS, list(self.get_parameter("home_joints").value))
        elif act == "grasp":
            self._send(self.grip_pub, GRIPPER_JOINT, [self.get_parameter("gripper_close").value])
        elif act == "release":
            self._send(self.grip_pub, GRIPPER_JOINT, [self.get_parameter("gripper_open").value])
        state = "running" if self.queue else "done"
        self.status_pub.publish(String(data=json.dumps({"state": state, "last": sg}, ensure_ascii=False)))

    def _send(self, pub, names, positions):
        msg = JointTrajectory()
        msg.joint_names = names
        pt = JointTrajectoryPoint()
        pt.positions = [float(p) for p in positions]
        sec = float(self.get_parameter("move_duration_sec").value)
        pt.time_from_start = Duration(sec=int(sec), nanosec=int((sec % 1) * 1e9))
        msg.points = [pt]
        pub.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(Controller())


if __name__ == "__main__":
    main()
