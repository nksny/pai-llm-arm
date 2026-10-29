"""Perception (camera版): 俯瞰カメラ画像から色分割で物体を検出し、ロボット基準座標で /perception/objects に配信。

真値(perception_node.py)の置き換え。Gazebo の物体位置は一切使わず、
  1. HSV 色空間で赤/青/黄/緑のマスクを作る
  2. 彩度でブロック(純色)とトレイ(淡色)を区別し、連結成分ごとに位置を取る
  3. ピンホールモデルでピクセル → 物体上面の高さの平面 → ロボット基準 (x,y,z) に逆投影する
カメラは真下向きで位置・画角は既知(ワールド SDF と同じ値をパラメータで持つ)。
検出結果を描いたデバッグ画像を /perception/debug_image に出す。
"""
import json
import math
import time

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

# 物体クラス: HSV(OpenCV: H 0-179, S/V 0-255) の範囲と種別。
# ブロック(純色)は S≈255、トレイ(淡色)は S≈75-160 なので、同系色でも彩度で分ける
# (面積で分けると、トレイに載ったブロックが同色の塊として繋がり見失う)。
# 木目のテーブルは H≈13-14, S≈140 なので赤(H≤6)と黄(H≥20)の間に入れない。
CLASSES = {
    "赤いブロック":   ("block", [((0, 220, 60), (6, 255, 255)), ((172, 220, 60), (179, 255, 255))]),
    "青いブロック":   ("block", [((100, 220, 60), (130, 255, 255))]),
    "黄色いブロック": ("block", [((20, 220, 80), (35, 255, 255))]),
    "赤いトレイ":     ("tray",  [((0, 40, 60), (6, 200, 255)), ((172, 40, 60), (179, 200, 255))]),
    "青いトレイ":     ("tray",  [((100, 60, 60), (130, 200, 255))]),
    "緑のトレイ":     ("tray",  [((45, 60, 60), (85, 255, 255))]),
}
# 種別ごとの高さ[m]: (上面の高さ, 中心の高さ)。逆投影の平面と、出力する z に使う
HEIGHTS = {"block": (0.04, 0.02), "tray": (0.005, 0.0025)}


class CameraPerception(Node):
    def __init__(self):
        super().__init__("perception_camera")
        self.declare_parameter("image_topic", "/overhead_camera/image")
        self.declare_parameter("camera_xyz", [0.13, 0.0, 1.715])   # 世界座標。真下向き(pitch +90°)
        self.declare_parameter("horizontal_fov", 0.9)
        self.declare_parameter("robot_origin_xyz", [0.0, 0.0, 1.015])
        self.declare_parameter("table_z", 1.015)
        self.declare_parameter("min_area_px", 300)      # これ未満の連結成分はノイズとして捨てる
        self.declare_parameter("stale_sec", 5.0)        # 見失った物体を保持する時間
        self.declare_parameter("period_sec", 0.5)
        self.cam = list(self.get_parameter("camera_xyz").value)
        self.origin = list(self.get_parameter("robot_origin_xyz").value)
        self.table_z = float(self.get_parameter("table_z").value)
        self.hfov = float(self.get_parameter("horizontal_fov").value)
        self.bridge = CvBridge()
        self.objects = {}      # label -> [x,y,z] (ロボット基準)
        self.seen = {}         # label -> 最終検出時刻
        self.frames = 0
        self.pub = self.create_publisher(String, "/perception/objects", 10)
        self.dbg_pub = self.create_publisher(Image, "/perception/debug_image", 2)
        self.create_subscription(Image, self.get_parameter("image_topic").value, self.on_image, 2)
        self.create_subscription(String, "/perception/set", self.on_set, 10)
        self.create_timer(float(self.get_parameter("period_sec").value), self.tick)
        self.get_logger().info(f"perception(camera): {self.get_parameter('image_topic').value}")

    # ---- 逆投影 -------------------------------------------------------------
    def pixel_to_robot(self, u, v, top_h, w, h):
        """画素 (u,v) にある高さ top_h の面上の点 → ロボット基準 (x,y)。
        カメラ座標: x=前(真下), y=左, z=上。画像右 = -y, 画像下 = -z。pitch +90° なので
        カメラ z 軸 = 世界 +x, カメラ y 軸 = 世界 +y。"""
        f = (w / 2.0) / math.tan(self.hfov / 2.0)
        depth = self.cam[2] - (self.table_z + top_h)
        yc = -(u - w / 2.0) * depth / f
        zc = -(v - h / 2.0) * depth / f
        wx, wy = self.cam[0] + zc, self.cam[1] + yc
        return wx - self.origin[0], wy - self.origin[1]

    # ---- 検出 ---------------------------------------------------------------
    def on_image(self, msg: Image):
        img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        h, w = img.shape[:2]
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        dbg = img.copy()
        min_area = int(self.get_parameter("min_area_px").value)
        now = time.time()
        found = {}
        for label, (kind, ranges) in CLASSES.items():
            mask = None
            for lo, hi in ranges:
                m = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
                mask = m if mask is None else cv2.bitwise_or(mask, m)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            n, _, stats, cents = cv2.connectedComponentsWithStats(mask)
            best = None
            for i in range(1, n):
                x, y, bw, bh, area = stats[i]
                if area >= min_area and (best is None or area > best[4]):
                    best = (x, y, bw, bh, area, cents[i])  # 同じラベルは最大面積の成分を採用
            if best is None:
                continue
            x, y, bw, bh, area, c = best
            found[label] = (kind, (c[0], c[1]), int(area), [x, y, x + bw, y + bh])
        # トレイは上にブロックが載ると一部が隠れる。中心が矩形内にあるブロックの矩形を取り込み、外接矩形の中心をトレイ位置にする
        result = {}
        for label, (kind, c, area, box) in found.items():
            box = list(box)
            if kind == "tray":
                for _, (k2, c2, _, b2) in found.items():
                    if k2 == "block" and box[0] <= c2[0] <= box[2] and box[1] <= c2[1] <= box[3]:
                        box = [min(box[0], b2[0]), min(box[1], b2[1]), max(box[2], b2[2]), max(box[3], b2[3])]
                c = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
            top_h, center_h = HEIGHTS[kind]
            rx, ry = self.pixel_to_robot(c[0], c[1], top_h, w, h)
            result[label] = (round(rx, 3), round(ry, 3), round(center_h, 3), area, (box[0], box[1], box[2] - box[0], box[3] - box[1]))
        found = result
        for label, (rx, ry, rz, area, (x, y, bw, bh)) in found.items():
            self.objects[label] = [rx, ry, rz]
            self.seen[label] = now
            cv2.rectangle(dbg, (x, y), (x + bw, y + bh), (255, 255, 255), 1)
            cv2.putText(dbg, f"{rx:.2f},{ry:.2f}", (x, max(10, y - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        self.frames += 1
        if self.frames % 5 == 0:
            self.dbg_pub.publish(self.bridge.cv2_to_imgmsg(dbg, encoding="bgr8"))

    def tick(self):
        stale = float(self.get_parameter("stale_sec").value)
        now = time.time()
        for label in [k for k, t in self.seen.items() if now - t > stale]:
            self.objects.pop(label, None); self.seen.pop(label, None)
        if self.objects:
            self.pub.publish(String(data=json.dumps(self.objects, ensure_ascii=False)))

    def on_set(self, msg: String):
        self.objects.update(json.loads(msg.data))
        for k in json.loads(msg.data):
            self.seen[k] = time.time()


def main():
    rclpy.init()
    rclpy.spin(CameraPerception())


if __name__ == "__main__":
    main()
