"""Monitor: 実行完了後に物体位置を再観測し、目標達成を判定。失敗なら /monitor/replan を発行(閉ループ)。

判定: 計画中の各 release の直前にある move_to を「置き位置」とみなし、
その水平位置の近くにいずれかの物体があれば成功。無ければ把持失敗/落下として再計画を要求する。
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
        self.objects = {}
        self.plan = None
        self.replan_pub = self.create_publisher(String, "/monitor/replan", 10)
        self.result_pub = self.create_publisher(String, "/monitor/result", 10)
        self.create_subscription(String, "/perception/objects", self.on_objects, 10)
        self.create_subscription(String, "/plan/subgoals", self.on_plan, 10)
        self.create_subscription(String, "/controller/status", self.on_status, 10)
        self.pending_check = None
        self.create_timer(0.2, self.tick)
        self.get_logger().info("monitor ready")

    def on_objects(self, msg):
        self.objects = json.loads(msg.data)

    def on_plan(self, msg):
        self.plan = json.loads(msg.data)

    def on_status(self, msg):
        st = json.loads(msg.data)
        if st["state"] == "failed":
            self._replan(st["reason"])
        elif st["state"] == "done":
            # 物体が静止し perception が更新されるのを待ってから判定
            self.pending_check = time.time() + float(self.get_parameter("settle_sec").value)

    def tick(self):
        if self.pending_check and time.time() >= self.pending_check:
            self.pending_check = None
            self._check_goal()

    def _check_goal(self):
        if not self.plan or "subgoals" not in self.plan:
            return
        tol = float(self.get_parameter("reach_tolerance_m").value)
        targets = place_targets(self.plan["subgoals"])
        if not targets:
            self.result_pub.publish(String(data="success: no placement in plan"))
            return
        missing = []
        for gx, gy, _ in targets:
            hit = [n for n, p in self.objects.items()
                   if ((p[0] - gx) ** 2 + (p[1] - gy) ** 2) ** 0.5 <= tol and p[2] > 0.005]
            if hit:
                self.get_logger().info(f"goal ({gx:.2f},{gy:.2f}) reached by {hit}")
            else:
                missing.append((gx, gy))
        if not missing:
            self.result_pub.publish(String(data=f"success: {len(targets)} placement(s) verified"))
            return
        where = ", ".join(f"({x:.2f},{y:.2f})" for x, y in missing)
        self._replan(f"置き位置 {where} に物体がありません。把持失敗または落下の可能性。")

    def _replan(self, reason: str):
        self.get_logger().warn(f"replan requested: {reason}")
        self.result_pub.publish(String(data=f"failure: {reason}"))
        self.replan_pub.publish(String(data=reason))


def main():
    rclpy.init()
    rclpy.spin(Monitor())


if __name__ == "__main__":
    main()
