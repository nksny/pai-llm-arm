"""Planner: 自然言語指示 + 物体座標 → サブゴール列(JSON)。LLM(Claude API)はイベント駆動でのみ呼ぶ。

安全層: 出力はJSONスキーマで固定語彙(move_to/grasp/release/home)に制約し、さらに到達範囲チェックで
物理的に不可能な計画を弾く。Monitorからの再計画要求は max_replans 回まで受け付ける。
"""
import json
import os
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

SYSTEM_PROMPT = """あなたは卓上ロボットアーム(CRANE+ V2, 4軸+グリッパ)のタスクプランナーです。
人の指示と、テーブル上の物体一覧(表示名と中心座標[m], ロボット基準: x前方, y左, z上, テーブル面がz=0)を受け取り、
サブゴール列をJSONで出力します。

action:
- move_to: 把持点(グリッパ中央)を target=[x,y,z] へ動かす
- grasp: グリッパを閉じる / release: 開く / home: 初期姿勢へ

ルール:
- 到達可能範囲: 原点からの水平距離 0.06〜0.21 m、z は 0.0〜0.15 m。範囲外なら error に理由を書き subgoals は空にする。
- ブロックは一辺4cm。把持はブロック中心の高さ(z≈0.02)で行う。
- 手順: release → 対象の上方(z=0.09)へ move_to → 対象高さへ move_to → grasp → 上方へ退避 → 目的地上方へ move_to → 目的地の高さ(z=0.03)へ move_to → release → 上方へ退避 → home
- トレイに置く場合は、トレイ中心座標を目的地にする。複数物体なら1つずつ順に行う。
- 指示が曖昧な場合は物体一覧から最も妥当な解釈を選び、note に根拠を1行で書く。
- 各 move_to の note には目的を短く書く(例: "赤いブロック上方")。"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "subgoals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["move_to", "grasp", "release", "home"]},
                    "target": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "note": {"type": "string"},
                },
                "required": ["action", "note"],
                "additionalProperties": False,
            },
        },
        "error": {"type": "string"},
    },
    "required": ["subgoals", "error"],
    "additionalProperties": False,
}

R_MIN, R_MAX, Z_MIN, Z_MAX = 0.05, 0.22, 0.0, 0.16


class Planner(Node):
    def __init__(self):
        super().__init__("planner")
        self.declare_parameter("model", "claude-opus-5")
        self.declare_parameter("max_retries", 3)
        self.declare_parameter("max_replans", 2)
        self.declare_parameter("history_turns", 6)
        self.objects = {}
        self.last_instruction = ""
        self.replans = 0
        self.history = []  # 会話履歴（「さっき置いた場所」などの参照指示に対応）
        self.pub = self.create_publisher(String, "/plan/subgoals", 10)
        self.create_subscription(String, "/perception/objects", self.on_objects, 10)
        self.create_subscription(String, "/task/instruction", self.on_instruction, 10)
        self.create_subscription(String, "/monitor/replan", self.on_replan, 10)
        import anthropic  # APIキーは環境変数 ANTHROPIC_API_KEY のみ
        self.client = anthropic.Anthropic()
        self.get_logger().info(f"planner ready (model={self.get_parameter('model').value})")

    def on_objects(self, msg: String):
        self.objects = json.loads(msg.data)

    def on_instruction(self, msg: String):
        self.last_instruction = msg.data
        self.replans = 0
        self.get_logger().info(f"instruction: {msg.data}")
        self.plan(f"指示: {msg.data}")

    def on_replan(self, msg: String):
        if self.replans >= int(self.get_parameter("max_replans").value):
            self.get_logger().error(f"replan limit reached; giving up: {msg.data}")
            return
        self.replans += 1
        self.get_logger().warn(f"replan #{self.replans}: {msg.data}")
        self.plan(
            f"指示: {self.last_instruction}\n前回の実行は失敗しました。理由: {msg.data}\n"
            "現在の物体配置(最新)から計画し直してください。"
        )

    def plan(self, user_text: str):
        model = self.get_parameter("model").value
        retries = int(self.get_parameter("max_retries").value)
        content = f"{user_text}\n物体一覧: {json.dumps(self.objects, ensure_ascii=False)}"
        self.history.append({"role": "user", "content": content})
        keep = 2 * int(self.get_parameter("history_turns").value)
        self.history = self.history[-keep:]
        t0 = time.time()
        for attempt in range(retries):
            try:
                res = self.client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=self.history,
                    output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
                )
                if res.stop_reason == "refusal":
                    raise RuntimeError("model refused")
                text = next(b.text for b in res.content if b.type == "text")
                data = json.loads(text)
                self._validate(data)
                self.history.append({"role": "assistant", "content": text})
                out = {"error": data["error"]} if data["error"] else {"subgoals": data["subgoals"]}
                self.pub.publish(String(data=json.dumps(out, ensure_ascii=False)))
                self.get_logger().info(f"plan ({time.time()-t0:.1f}s, {len(data['subgoals'])} steps): {text}")
                self._log(content, text, res.usage)
                return
            except Exception as e:  # パース失敗・制約違反・API障害 → 再試行
                self.get_logger().warn(f"plan attempt {attempt+1} failed: {e}")
                if self.history and self.history[-1]["role"] == "user" and attempt < retries - 1:
                    self.history[-1]["content"] = content + f"\n(前回の出力は不正でした: {e}。制約を守って出し直してください)"
                time.sleep(1.0)
        self.history.pop()  # 失敗したuser発話を履歴から外す
        self.get_logger().error("planning failed after retries")

    @staticmethod
    def _validate(data: dict):
        if data.get("error"):
            return
        if not data["subgoals"]:
            raise ValueError("empty plan")
        for sg in data["subgoals"]:
            if sg["action"] == "move_to":
                if "target" not in sg:
                    raise ValueError("move_to without target")
                x, y, z = sg["target"]
                r = (x * x + y * y) ** 0.5
                if not (R_MIN <= r <= R_MAX) or not (Z_MIN <= z <= Z_MAX):
                    raise ValueError(f"target out of reach {sg['target']}")

    def _log(self, prompt: str, response: str, usage):
        path = os.path.expanduser("~/pai_work/pai-final-task/logs/llm.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rec = {"t": time.time(), "prompt": prompt, "response": response,
               "in_tokens": getattr(usage, "input_tokens", None), "out_tokens": getattr(usage, "output_tokens", None)}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    rclpy.init()
    rclpy.spin(Planner())


if __name__ == "__main__":
    main()
