#!/usr/bin/env bash
# コンテナ内で実行: LLM を使わず固定計画(赤→青トレイ)を流し、ブロックの物性(摩擦・質量)による結果の違いを調べる。
#   [TESTLIFT=1] bash scripts/probe_physics.sh <mu> <mass> [tag]   (TESTLIFT=1: 把持後に 1cm の試し持ち上げと 6cm の試し移動を挟む)
# 出力(JSON 1行): 結果、置き位置の真値誤差、保持中の最大高さ、真値の時系列ファイル。
# planner は止めておく(再計画で LLM を呼ばないため)。再計画要求が出た時点で失敗とみなす。
source /opt/ros/humble/setup.bash
cd ~/pai_work/pai-final-task
MU=$1; MASS=$2; TAG=${3:-probe}
pkill -f "[l]ib/pai_llm_arm/planner" 2>/dev/null
RED_MU=$MU RED_MASS=$MASS bash scripts/setup_world.sh >/dev/null; sleep 3
TEST=""; [ "${TESTLIFT:-0}" = 1 ] && TEST='{"action":"move_to","target":[0.10,0.05,0.03],"note":"試し持ち上げ"},{"action":"move_to","target":[0.10,0.11,0.03],"note":"試し移動"},'
PLAN='{"subgoals":[{"action":"release","note":"open"},{"action":"move_to","target":[0.10,0.05,0.09],"note":"above red"},{"action":"move_to","target":[0.10,0.05,0.02],"note":"red"},{"action":"grasp","note":"grasp"},'"$TEST"'{"action":"move_to","target":[0.10,0.05,0.09],"note":"lift"},{"action":"move_to","target":[0.10,0.14,0.09],"note":"above tray"},{"action":"move_to","target":[0.10,0.14,0.035],"note":"tray"},{"action":"release","note":"release"},{"action":"move_to","target":[0.10,0.14,0.09],"note":"up"},{"action":"home","note":"home"}]}'
mkdir -p logs/trace; TR=logs/trace/${TAG}_mu${MU}_m${MASS}_$(date +%H%M%S).txt
bash scripts/trace_truth.sh red_block "$TR" & TRP=$!
ros2 topic pub --once -w 1 /task/instruction std_msgs/String "{data: 'probe'}" >/dev/null 2>&1
ros2 topic pub --once -w 2 /plan/subgoals std_msgs/String "{data: '$PLAN'}" >/dev/null 2>&1
RES=$(python3 scripts/wait_outcome.py 150 | cut -c1-70)
kill $TRP 2>/dev/null; wait $TRP 2>/dev/null
python3 - "$TAG" "$MU" "$MASS" "$RES" "$TR" <<'PY'
import sys, json, math
tag, mu, mass, res, tr = sys.argv[1:6]
rows = [l.split() for l in open(tr) if len(l.split()) == 4]
pts = [(float(t), float(x), float(y), float(z)) for t, x, y, z in rows]
fx, fy, fz = pts[-1][1:] if pts else (float('nan'),)*3
maxz = max(p[3] for p in pts) if pts else float('nan')
# 保持中(z が机上 2cm 以上)の水平移動量: 把持点の軌道と比べたいので最高点時刻と離した直後の位置も残す
held = [p for p in pts if p[3] > 1.015 + 0.045]
print(json.dumps({"tag": tag, "mu": float(mu), "mass": float(mass), "result": res,
    "success": res.startswith("success"), "place_err_cm": round(100*math.hypot(fx-0.10, fy-0.14), 1),
    "final_xy": [round(fx,3), round(fy,3)], "max_z": round(maxz-1.015, 3), "held_samples": len(held), "trace": tr}, ensure_ascii=False))
PY
