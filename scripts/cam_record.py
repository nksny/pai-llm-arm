#!/usr/bin/env python3
"""コンテナ内で実行: カメラ知覚のデバッグ画像(/perception/debug_image)を 10fps の動画に落とす(録画の PiP 用)。
   python3 scripts/cam_record.py videos/<name>_cam   -> <name>_cam.mp4 と開始時刻 <name>_cam.start。SIGTERM/SIGINT で終了。
画像は 4Hz 程度で不定期に届くので、10Hz のタイマで最新フレームを書き続けて壁時計と同期させる。"""
import signal, sys, time
import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

out = sys.argv[1]
FPS = 10
rclpy.init(); n = Node("cam_record"); b = CvBridge(); last = [None]; writer = [None]
n.create_subscription(Image, "/perception/debug_image", lambda m: last.__setitem__(0, b.imgmsg_to_cv2(m, "bgr8")), 2)
t_start = time.time(); open(out + ".start", "w").write(f"{t_start:.6f}\n")
frames = 0
def stop(*_):
    if writer[0]: writer[0].release()
    print(f"wrote {out}.mp4 ({frames} frames)"); sys.exit(0)
signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
while True:
    rclpy.spin_once(n, timeout_sec=0.02)
    due = int((time.time() - t_start) * FPS)
    if last[0] is not None and frames < due:
        if writer[0] is None:
            h, w = last[0].shape[:2]
            writer[0] = cv2.VideoWriter(out + ".mp4", cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h))
            frames = due  # 最初のフレームが来るまでの空白は、開始時刻のオフセットで吸収する
            open(out + ".start", "w").write(f"{t_start + frames / FPS:.6f}\n")
        while frames < due:
            writer[0].write(last[0]); frames += 1
