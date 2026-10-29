"""Perception: 物体の座標(ロボット基準, m)を /perception/objects に JSON で配信。

この環境の Gazebo は Ignition(Fortress) のため /model_states は存在しない。
`ign topic -e -t /world/<world>/pose/info -n 1` の出力(名前付き)を周期的にパースして真値を得る。
将来の置換候補: カメラ画像 + VLM による座標推定。
"""
import json
import re
import subprocess

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Gazeboのモデル名 → 指示で使う表示名
DEFAULT_TRACKED = {
    "red_block": "赤いブロック",
    "blue_block": "青いブロック",
    "yellow_block": "黄色いブロック",
    "blue_tray": "青いトレイ",
    "green_tray": "緑のトレイ",
    "red_tray": "赤いトレイ",
}

_POSE_RE = re.compile(
    r'pose \{\s*name: "([^"]+)"\s*id: \d+\s*position \{\s*(?:x: ([-\d.eE+]+)\s*)?(?:y: ([-\d.eE+]+)\s*)?(?:z: ([-\d.eE+]+)\s*)?\}',
    re.S,
)


def parse_pose_info(text: str) -> dict:
    """ign topic -e の protobuf テキストからモデル名→[x,y,z]。無い成分は0。"""
    out = {}
    for name, x, y, z in _POSE_RE.findall(text):
        out[name] = [float(x or 0.0), float(y or 0.0), float(z or 0.0)]
    return out


class Perception(Node):
    def __init__(self):
        super().__init__("perception")
        self.declare_parameter("world", "default")
        self.declare_parameter("robot_origin_xyz", [0.0, 0.0, 1.015])  # ロボットbase_linkの世界座標
        self.declare_parameter("period_sec", 0.5)
        self.declare_parameter("tracked_json", json.dumps(DEFAULT_TRACKED, ensure_ascii=False))
        self.tracked = json.loads(self.get_parameter("tracked_json").value)
        self.origin = list(self.get_parameter("robot_origin_xyz").value)
        self.topic = f"/world/{self.get_parameter('world').value}/pose/info"
        self.objects = {}
        self.pub = self.create_publisher(String, "/perception/objects", 10)
        self.create_subscription(String, "/perception/set", self.on_set, 10)
        self.create_timer(float(self.get_parameter("period_sec").value), self.tick)
        self.get_logger().info(f"perception: ground truth from {self.topic}")

    def tick(self):
        try:
            res = subprocess.run(
                ["ign", "topic", "-e", "-t", self.topic, "-n", "1"],
                capture_output=True, text=True, timeout=3.0,
            )
            poses = parse_pose_info(res.stdout)
        except Exception as e:  # ign未起動など
            self.get_logger().warn(f"pose read failed: {e}", throttle_duration_sec=5.0)
            poses = {}
        for model, label in self.tracked.items():
            if model in poses:
                p = poses[model]
                self.objects[label] = [round(p[i] - self.origin[i], 3) for i in range(3)]
        if self.objects:
            self.pub.publish(String(data=json.dumps(self.objects, ensure_ascii=False)))

    def on_set(self, msg: String):
        # デバッグ用の手動注入: ros2 topic pub --once /perception/set std_msgs/String "{data: '{\"赤いブロック\": [0.12, 0.06, 0.02]}'}"
        self.objects.update(json.loads(msg.data))


def main():
    rclpy.init()
    rclpy.spin(Perception())


if __name__ == "__main__":
    main()
