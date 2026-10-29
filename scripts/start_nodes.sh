#!/usr/bin/env bash
# コンテナ内で実行: pai_llm_arm の4ノードをまとめて起動(ログは /tmp/*.log)。
# 事前に demo_gazebo.launch.py と scripts/setup_world.sh を実行しておく。
#   PERCEPTION=camera bash scripts/start_nodes.sh   → 俯瞰カメラ画像からの知覚(真値を使わない)
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash
source ~/pai_work/pai-final-task/ros2_ws/install/setup.bash
pkill -f "[l]ib/pai_llm_arm/" 2>/dev/null; sleep 1
[ -f ~/pai_work/pai-final-task/.env ] && { set -a; . ~/pai_work/pai-final-task/.env; set +a; }
PARAMS=~/pai_work/pai-final-task/ros2_ws/src/pai_llm_arm/config/params.yaml
PERC=perception; [ "${PERCEPTION:-}" = camera ] && PERC=perception_camera
for n in $PERC controller monitor planner; do
  ros2 run pai_llm_arm $n --ros-args --params-file $PARAMS > /tmp/$n.log 2>&1 &
  echo "started $n (log: /tmp/$n.log)"
done
sleep 3; tail -n1 /tmp/planner.log
