#!/usr/bin/env bash
# コンテナ内で実行: 4種のデモを録画なしで繰り返し、成功率などを logs/eval.jsonl に追記する。
#   bash scripts/eval_batch.sh [rounds=5] [tag=truth]
# 集計: python3 scripts/eval_summary.py
set -o pipefail
cd ~/pai_work/pai-final-task
source /opt/ros/humble/setup.bash
ROUNDS=${1:-5}; TAG=${2:-truth}
mkdir -p logs; touch logs/llm.jsonl

run_one() {  # name instruction [disturb_after_grasp_sec]
  local NAME=$1 INSTR=$2 DISTURB_AT=${3:-}
  bash scripts/reset_world.sh >/dev/null; sleep 3
  local LLM0=$(wc -l < logs/llm.jsonl) MON0=$(wc -l < /tmp/monitor.log) PLN0=$(wc -l < /tmp/planner.log)
  timeout -s KILL 300 ros2 topic echo --once /monitor/result > /tmp/eval_result.txt 2>/dev/null &
  local WAIT=$!
  sleep 1; bash scripts/say.sh "$INSTR" >/dev/null; local T0=$(date +%s.%N)
  if [ -n "$DISTURB_AT" ]; then
    (python3 scripts/wait_status.py '"action": "grasp"' 120 >/dev/null && sleep "$DISTURB_AT" && bash scripts/disturb.sh >/dev/null) &
  fi
  wait $WAIT; local T1=$(date +%s.%N)
  python3 scripts/eval_record.py "$TAG" "$NAME" "$INSTR" "$T0" "$T1" /tmp/eval_result.txt "$LLM0" "$MON0" "$PLN0" >> logs/eval.jsonl
  tail -n1 logs/eval.jsonl | cut -c1-160
}

for r in $(seq 1 "$ROUNDS"); do
  echo "== round $r/$ROUNDS ($TAG)"
  run_one basic     "赤いブロックを青いトレイに置いて"
  run_one ambiguous "青いブロックを同じ色のトレイに置いて"
  run_one sort      "ブロックを色ごとに仕分けて"
  run_one recover   "赤いブロックを緑のトレイに置いて" 2
done
echo "done: logs/eval.jsonl"
