#!/usr/bin/env bash
# コンテナ内で実行: 自然言語指示を送る。例: bash scripts/say.sh "赤いブロックを青いトレイに置いて"
source /opt/ros/humble/setup.bash
# 2 購読者(planner, monitor)を待ってから 1 秒間隔で 2 回送る(--once だと稀に片方へ届かない。planner 側で重複は無視)
ros2 topic pub -t 2 -w 2 /task/instruction std_msgs/String "{data: '$1'}" >/dev/null
echo "sent: $1  (結果: ros2 topic echo /monitor/result)"
