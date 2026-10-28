#!/usr/bin/env bash
# コンテナ内で実行: 自然言語指示を送る。例: bash scripts/say.sh "赤いブロックを青いトレイに置いて"
source /opt/ros/humble/setup.bash
ros2 topic pub --once /task/instruction std_msgs/String "{data: '$1'}" >/dev/null
echo "sent: $1  (結果: ros2 topic echo /monitor/result)"
