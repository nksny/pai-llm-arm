#!/usr/bin/env bash
# コンテナ内で実行: 妨害デモ用。指定物体を別の位置へ瞬間移動させる(デフォルト: 赤いブロックを (0.16, 0.03) へ)。
#   bash scripts/disturb.sh [name] [x] [y]   (ロボット基準の x,y。テーブル面上に置く)
source /opt/ros/humble/setup.bash
NAME=${1:-red_block}; X=${2:-0.16}; Y=${3:-0.03}; Z=$(echo "1.015+0.03" | bc)
ign service -s /world/default/set_pose --reqtype ignition.msgs.Pose --reptype ignition.msgs.Boolean --timeout 2000 \
  --req "name: \"$NAME\", position: {x: $X, y: $Y, z: $Z}, orientation: {w: 1.0}" >/dev/null && echo "moved $NAME to ($X, $Y)"
case "$NAME" in red_block) JA="赤いブロック";; blue_block) JA="青いブロック";; yellow_block) JA="黄色いブロック";; *) JA="$NAME";; esac
ros2 topic pub --once -w 1 /demo/event std_msgs/String "{data: '妨害: ${JA} を手で別の場所へ動かした'}" >/dev/null 2>&1 || true
