#!/usr/bin/env python3
"""コンテナ内で実行: デモ中のイベント(指示・計画・実行・妨害・再計画・結果)を壁時計時刻付きで記録する。
   python3 scripts/event_log.py <outfile>   (SIGTERM で終了)。annotate.sh が字幕生成に使う。
行形式: <unix時刻>\t<種別>\t<テキスト>"""
import json, sys, time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

out = open(sys.argv[1], "a", buffering=1)
def w(kind, text=""):
    out.write(f"{time.time():.3f}\t{kind}\t{text}\n")

rclpy.init(); n = Node("event_log")
def on_plan(m):
    d = json.loads(m.data)
    w("plan", f"{len(d['subgoals'])}ステップ" if "subgoals" in d else f"計画不可: {d['error']}")
n.create_subscription(String, "/plan/subgoals", on_plan, 10)
def on_ctrl(m):
    d = json.loads(m.data); sg = d.get("last", {})
    if sg.get("action") in ("grasp", "release", "home"):
        w("step", sg["action"] + ("" if not sg.get("note") else ": " + sg["note"]))
    if d["state"] == "done":
        w("done")
n.create_subscription(String, "/controller/status", on_ctrl, 10)
n.create_subscription(String, "/monitor/status", lambda m: w("replan", m.data), 10)
n.create_subscription(String, "/monitor/result", lambda m: w("result", m.data), 10)
n.create_subscription(String, "/demo/event", lambda m: w("demo", m.data), 10)   # disturb.sh などが通知
rclpy.spin(n)
