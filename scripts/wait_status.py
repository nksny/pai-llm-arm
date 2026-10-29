#!/usr/bin/env python3
"""コンテナ内で実行: /controller/status に指定文字列を含むメッセージが来るまで待つ(デモの妨害タイミング用)。
   python3 scripts/wait_status.py '"action": "grasp"' [timeout_sec]"""
import sys, time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

needle = sys.argv[1]; limit = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
rclpy.init(); node = Node("wait_status"); hit = []
node.create_subscription(String, "/controller/status", lambda m: hit.append(m.data) if needle in m.data else None, 10)
t0 = time.time()
while not hit and time.time() - t0 < limit:
    rclpy.spin_once(node, timeout_sec=0.2)
print("matched" if hit else "timeout"); sys.exit(0 if hit else 1)
