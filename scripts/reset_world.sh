#!/usr/bin/env bash
# コンテナ内で実行: ブロックとトレイを初期位置に戻し、グリッパを開く。
source /opt/ros/humble/setup.bash
set_pose() { ign service -s /world/default/set_pose --reqtype ignition.msgs.Pose --reptype ignition.msgs.Boolean --timeout 2000 \
  --req "name: \"$1\", position: {x: $2, y: $3, z: $4}, orientation: {w: 1.0}" >/dev/null 2>&1; }
set_pose red_block    0.10  0.05 1.04
set_pose blue_block   0.15 -0.03 1.04
set_pose yellow_block 0.09 -0.08 1.04
set_pose blue_tray    0.10  0.14 1.02
set_pose green_tray   0.17  0.10 1.02
set_pose red_tray     0.16 -0.11 1.02
ros2 topic pub --once /crane_plus_gripper_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [crane_plus_joint_hand], points: [{positions: [-0.5], time_from_start: {sec: 1}}]}" >/dev/null
ros2 topic pub --once /crane_plus_arm_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [crane_plus_joint1, crane_plus_joint2, crane_plus_joint3, crane_plus_joint4], points: [{positions: [0.0, 0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}" >/dev/null
echo "world reset"
