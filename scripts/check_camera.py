#!/usr/bin/env python3
"""コンテナ内で実行: カメラ知覚(/perception/objects)と Gazebo 真値を比較し、物体ごとの位置誤差[mm]を表示する。
   python3 scripts/check_camera.py [samples=5]   (perception_camera を起動した状態で)"""
import json, subprocess, sys, time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from pai_llm_arm.perception_node import parse_pose_info, DEFAULT_TRACKED

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
ORIGIN = [0.0, 0.0, 1.015]
rclpy.init(); node = Node("check_camera"); latest = {}
node.create_subscription(String, "/perception/objects", lambda m: latest.update(json.loads(m.data)), 10)
errs = {}
for i in range(N):
    for _ in range(10):
        rclpy.spin_once(node, timeout_sec=0.1)
    res = subprocess.run(["ign", "topic", "-e", "-t", "/world/default/pose/info", "-n", "1"], capture_output=True, text=True, timeout=3)
    truth = parse_pose_info(res.stdout)
    for model, label in DEFAULT_TRACKED.items():
        if model in truth and label in latest:
            t = [truth[model][k] - ORIGIN[k] for k in range(3)]; c = latest[label]
            errs.setdefault(label, []).append((abs(c[0]-t[0])*1000, abs(c[1]-t[1])*1000, abs(c[2]-t[2])*1000, t, c))
    time.sleep(0.5)
print(f"{'物体':10s} {'|dx|':>6s} {'|dy|':>6s} {'|dz|':>6s}  truth -> camera (最後のサンプル)")
allxy = []
for label, es in errs.items():
    dx = sum(e[0] for e in es)/len(es); dy = sum(e[1] for e in es)/len(es); dz = sum(e[2] for e in es)/len(es)
    allxy += [max(e[0], e[1]) for e in es]
    print(f"{label:10s} {dx:6.1f} {dy:6.1f} {dz:6.1f}  {[round(v,3) for v in es[-1][3]]} -> {es[-1][4]}")
missing = [l for l in DEFAULT_TRACKED.values() if l not in latest]
print(f"平均 max(|dx|,|dy|) = {sum(allxy)/max(len(allxy),1):.1f} mm, 未検出: {missing or 'なし'}")
