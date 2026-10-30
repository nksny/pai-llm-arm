"""Monitor: 実行完了後に物体位置を再観測し、目標達成を判定。失敗なら /monitor/replan を発行(閉ループ)。

判定: 計画中の各 release の直前にある move_to を「置き位置」とみなし、
その水平位置の近くにいずれかの物体があれば成功。無ければ把持失敗/落下として再計画を要求する。
/monitor/result には最終結果(success/failure)のみを流す。再計画の要求は /monitor/replan と /monitor/status に出す。

実行中の監視(10/30 追加): grasp 時に把持位置へ最も近い物体を「運搬対象」として覚え、把持位置から離れる move_to(旋回)が
完了した時点で運搬対象がその目標付近に無ければ「運搬中に手元から離れた」と判定し、残りの計画を中止して即座に再計画を要求する。
滑りやすい物体の滑落や、人による持ち去りを完了前に検知するため。
"""
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def place_targets(subgoals):
    """release の直前の move_to 座標を列挙(最初の release が「開く」だけの場合は除外)。"""
    out, last_move, grasped = [], None, False
    for sg in subgoals:
        if sg["action"] == "move_to":
            last_move = sg["target"]
        elif sg["action"] == "grasp":
            grasped = True
        elif sg["action"] == "release" and grasped and last_move is not None:
            out.append(last_move)
            grasped = False
    return out


class Monitor(Node):
    def __init__(self):
        super().__init__("monitor")
        self.declare_parameter("reach_tolerance_m", 0.03)
        self.declare_parameter("settle_sec", 1.5)
        self.declare_parameter("max_replans", 2)
        self.declare_parameter("container_keyword", "トレイ")  # 置き場(トレイ)自身は「置かれた物体」とみなさない
        self.declare_parameter("carry_check_m", 0.05)   # 旋回後、運搬対象が目標からこれ以上離れていれば手元から離れたと判定
        self.declare_parameter("carry_check_delay_sec", 0.7)
        self.replans = 0
        self.carried = None        # 運搬対象の物体名
        self.grasp_xy = None       # 把持位置
        self.prev_sg = None        # 直前に dispatch されたサブゴール(status の last)
        self.pending_carry = None  # (時刻, 目標xy)
        self.objects = {}
        self.plan = None
        self.replan_pub = self.create_publisher(String, "/monitor/replan", 10)
        self.result_pub = self.create_publisher(String, "/monitor/result", 10)
        self.status_pub = self.create_publisher(String, "/monitor/status", 10)
        self.abort_pub = self.create_publisher(String, "/controller/abort", 10)
        self.create_subscription(String, "/task/instruction", self.on_instruction, 10)
        self.create_subscription(String, "/perception/objects", self.on_objects, 10)
        self.create_subscription(String, "/plan/subgoals", self.on_plan, 10)
        self.create_subscription(String, "/controller/status", self.on_status, 10)
        self.pending_check = None
        self.create_timer(0.2, self.tick)
        self.get_logger().info("monitor ready")

    def on_objects(self, msg):
        self.objects = json.loads(msg.data)

    def on_instruction(self, msg):
        self.replans = 0
        self.pending_check = None
        self._reset_carry()

    def _reset_carry(self):
        self.carried = self.grasp_xy = self.prev_sg = self.pending_carry = None

    def _movable(self):
        kw = str(self.get_parameter("container_keyword").value)
        return {n: p for n, p in self.objects.items() if not (kw and kw in n)}

    def _track_carry(self, sg):
        """controller が dispatch したサブゴール列から、運搬対象と旋回完了のタイミングを追う。"""
        prev, self.prev_sg = self.prev_sg, sg
        act = sg.get("action")
        if act == "grasp":
            if prev and prev.get("action") == "move_to":
                gx, gy = prev["target"][0], prev["target"][1]
                near = sorted(self._movable().items(), key=lambda kv: (kv[1][0] - gx) ** 2 + (kv[1][1] - gy) ** 2)
                if near and ((near[0][1][0] - gx) ** 2 + (near[0][1][1] - gy) ** 2) ** 0.5 < 0.04:
                    self.carried, self.grasp_xy = near[0][0], (gx, gy)
                    self.get_logger().info(f"carrying: {self.carried} from ({gx:.2f},{gy:.2f})")
            return
        if act == "release":
            self.carried = self.grasp_xy = None
            return
        # sg が dispatch された = prev の動作は完了している。prev が把持位置から離れる move_to なら運搬対象の位置を確認する
        if self.carried and prev and prev.get("action") == "move_to":
            px, py = prev["target"][0], prev["target"][1]
            if ((px - self.grasp_xy[0]) ** 2 + (py - self.grasp_xy[1]) ** 2) ** 0.5 > 0.05:
                self.pending_carry = (time.time() + float(self.get_parameter("carry_check_delay_sec").value), (px, py))

    def _check_carry(self):
        _, (tx, ty) = self.pending_carry
        self.pending_carry = None
        name = self.carried
        p = self.objects.get(name)
        if not name or p is None:
            return
        d = ((p[0] - tx) ** 2 + (p[1] - ty) ** 2) ** 0.5
        if d <= float(self.get_parameter("carry_check_m").value):
            self.get_logger().info(f"carry ok: {name} at ({p[0]:.2f},{p[1]:.2f}) near ({tx:.2f},{ty:.2f})")
            return
        reason = (f"運搬中に『{name}』が手元から離れました(現在 ({p[0]:.2f},{p[1]:.2f}), 把持位置 "
                  f"({self.grasp_xy[0]:.2f},{self.grasp_xy[1]:.2f}) の近く)。滑落または外部から動かされた可能性。")
        self.get_logger().warn(f"carry lost: {reason}")
        self.abort_pub.publish(String(data="carry lost"))
        self._reset_carry()
        self._replan(reason)

    def on_plan(self, msg):
        self.plan = json.loads(msg.data)

    def on_status(self, msg):
        st = json.loads(msg.data)
        if st["state"] == "failed":
            self._replan(st["reason"])
        elif st["state"] == "rejected":  # planner が実行不可能と判断 → 再計画せず最終結果
            self.result_pub.publish(String(data=f"failure: 計画不可: {st['reason']}"))
        elif st["state"] == "done":
            self.prev_sg = None
            # 物体が静止し perception が更新されるのを待ってから判定
            self.pending_check = time.time() + float(self.get_parameter("settle_sec").value)
        elif st["state"] == "running" and st.get("last"):
            self._track_carry(st["last"])

    def tick(self):
        if self.pending_carry and time.time() >= self.pending_carry[0]:
            self._check_carry()
        if self.pending_check and time.time() >= self.pending_check:
            self.pending_check = None
            self._check_goal()

    def _check_goal(self):
        if not self.plan or "subgoals" not in self.plan:
            return
        tol = float(self.get_parameter("reach_tolerance_m").value)
        targets = place_targets(self.plan["subgoals"])
        self.get_logger().info("objects at check: " + ", ".join(
            f"{n}=({p[0]:.3f},{p[1]:.3f},{p[2]:.3f})" for n, p in self.objects.items()))
        if not targets:
            self.result_pub.publish(String(data="success: no placement in plan"))
            return
        missing, used = [], set()  # 1つの物体が複数の置き位置を満たすことはない
        movable = self._movable()
        for gx, gy, _ in targets:
            hit = [n for n, p in movable.items()
                   if n not in used and ((p[0] - gx) ** 2 + (p[1] - gy) ** 2) ** 0.5 <= tol and p[2] > 0.005]
            if hit:
                used.add(hit[0])
                self.get_logger().info(f"goal ({gx:.2f},{gy:.2f}) reached by {hit[0]}")
            else:
                missing.append((gx, gy))
        if not missing:
            self.result_pub.publish(String(data=f"success: {len(targets)} placement(s) verified"))
            return
        where = ", ".join(f"({x:.2f},{y:.2f})" for x, y in missing)
        self._replan(f"置き位置 {where} に物体がありません。把持失敗または落下の可能性。")

    def _replan(self, reason: str):
        if self.replans >= int(self.get_parameter("max_replans").value):
            self.get_logger().error(f"replan limit reached: {reason}")
            self.result_pub.publish(String(data=f"failure: {reason} (再計画上限 {self.replans} 回に到達)"))
            return
        self.replans += 1
        self.get_logger().warn(f"replan #{self.replans} requested: {reason}")
        self.status_pub.publish(String(data=f"replan #{self.replans}: {reason}"))
        self.replan_pub.publish(String(data=reason))


def main():
    rclpy.init()
    rclpy.spin(Monitor())


if __name__ == "__main__":
    main()
