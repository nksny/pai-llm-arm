#!/usr/bin/env python3
"""コンテナ内で実行: /monitor/result(最終結果) か /monitor/status の再計画要求のどちらか早い方を待って表示する。
   python3 scripts/wait_outcome.py [timeout_sec]   (planner を止めた検査で、再計画要求を失敗として即座に拾う用途)"""
import sys, time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

limit = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
rclpy.init(); node = Node("wait_outcome"); got = []
node.create_subscription(String, "/monitor/result", lambda m: got.append(m.data), 10)
node.create_subscription(String, "/monitor/status", lambda m: got.append("replan: " + m.data) if m.data.startswith("replan") else None, 10)
t0 = time.time()
while not got and time.time() - t0 < limit:
    rclpy.spin_once(node, timeout_sec=0.2)
print(got[0] if got else "timeout")
