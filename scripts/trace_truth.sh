#!/usr/bin/env bash
# コンテナ内で実行: 指定モデルの真値位置(世界座標)を約 3 Hz でファイルに記録する。停止は kill。
#   bash scripts/trace_truth.sh <model> <outfile>
source /opt/ros/humble/setup.bash
NAME=$1; OUT=$2; : > "$OUT"
while true; do
  P=$(ign topic -e -t /world/default/pose/info -n 1 2>/dev/null | grep -A6 "name: \"$NAME\"" | grep -E "^ *(x|y|z):" | head -3 | awk '{printf "%s ", $2}')
  echo "$(date +%s.%N) $P" >> "$OUT"
done
