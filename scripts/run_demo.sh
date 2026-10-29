#!/usr/bin/env bash
# コンテナ内で実行: 1本のデモを録画付きで走らせる。
#   bash scripts/run_demo.sh <name> "<指示>" [妨害: 把持後に待つ秒数]
# 例: bash scripts/run_demo.sh basic "赤いブロックを青いトレイに置いて"
#     bash scripts/run_demo.sh recover "赤いブロックを緑のトレイに置いて" 3    # 把持(grasp)の3秒後に赤ブロックを動かす
set -o pipefail
cd ~/pai_work/pai-final-task
source /opt/ros/humble/setup.bash
NAME=$1; INSTR=$2; DISTURB_AT=${3:-}
bash scripts/reset_world.sh; sleep 3
rm -f "videos/$NAME.events"; python3 scripts/event_log.py "videos/$NAME.events" & EVLOG=$!
bash scripts/record.sh start "$NAME"; sleep 2
timeout -s KILL 300 ros2 topic echo --once /monitor/result > /tmp/result_$NAME.txt 2>/dev/null &
WAIT=$!
sleep 1; printf "%s\tinstruction\t%s\n" "$(date +%s.%N)" "$INSTR" >> "videos/$NAME.events"; bash scripts/say.sh "$INSTR"; T0=$(date +%s)
if [ -n "$DISTURB_AT" ]; then
  (python3 scripts/wait_status.py '"action": "grasp"' 120 >/dev/null && sleep "$DISTURB_AT" && bash scripts/disturb.sh) &
fi
wait $WAIT; T1=$(date +%s)
sleep 3; bash scripts/record.sh stop >/dev/null; kill $EVLOG 2>/dev/null
bash scripts/annotate.sh "$NAME" >/dev/null && echo "annotated: videos/${NAME}_sub.mp4"
echo "== $NAME: $((T1-T0))s  $(grep data /tmp/result_$NAME.txt)"
grep "plan (" /tmp/planner.log | tail -3 | cut -c1-100
