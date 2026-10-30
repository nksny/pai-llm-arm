#!/usr/bin/env bash
# デモ用ワールド整備: 既存の木ブロックを消し、色付きブロックとトレイを配置する。
# コンテナ内で、crane_plus_gazebo の launch 起動後に実行する。
# 座標は世界座標。テーブル面は z=1.015 (= ロボット base_link の高さ)
set -e
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash
WORLD=default
TABLE_Z=1.015
# ブロックの摩擦係数(既定 1.2)。環境変数で個別に変えられる: RED_MU=0.05 bash scripts/setup_world.sh
# 「見た目は同じでも滑りやすい個体」を作り、知覚からは分からない隠れた物性への対応を評価する用途
RED_MU=${RED_MU:-1.2}; BLUE_MU=${BLUE_MU:-1.2}; YELLOW_MU=${YELLOW_MU:-1.2}
RED_MASS=${RED_MASS:-0.02}; BLUE_MASS=${BLUE_MASS:-0.02}; YELLOW_MASS=${YELLOW_MASS:-0.02}

# 既存の木ブロックと、再実行時の旧デモ物体を消す
for m in wood_cube_5cm red_block blue_block yellow_block blue_tray green_tray red_tray; do
  ign service -s /world/$WORLD/remove --reqtype ignition.msgs.Entity --reptype ignition.msgs.Boolean \
    --timeout 2000 --req "name: \"$m\" type: MODEL" >/dev/null 2>&1 || true
done
sleep 1

box_sdf() {  # name size_xyz rgb mass [mu=1.2]
  local MU=${5:-1.2}
  cat <<SDF
<?xml version="1.0"?><sdf version="1.6"><model name="$1"><link name="link">
<inertial><mass>$4</mass><inertia><ixx>1e-5</ixx><iyy>1e-5</iyy><izz>1e-5</izz></inertia></inertial>
<collision name="c"><geometry><box><size>$2</size></box></geometry>
<surface><friction><ode><mu>$MU</mu><mu2>$MU</mu2></ode></friction></surface></collision>
<visual name="v"><geometry><box><size>$2</size></box></geometry>
<material><ambient>$3 1</ambient><diffuse>$3 1</diffuse></material></visual>
</link></model></sdf>
SDF
}
spawn() {  # name sdf x y z
  ros2 run ros_gz_sim create -world $WORLD -name "$1" -string "$2" -x "$3" -y "$4" -z "$5" >/dev/null 2>&1 \
    && echo "spawned $1 at ($3, $4)"
}
# ブロック 4cm (ロボット基準 x前方, y左)。赤は緑トレイの角(x≥0.13,y≥0.06)に乗らない位置にする(乗ると傾いて把持が不安定になる)
spawn red_block    "$(box_sdf red_block    "0.04 0.04 0.04" "1 0 0"   $RED_MASS    $RED_MU)"    0.10  0.05 $(echo "$TABLE_Z+0.03" | bc)
spawn blue_block   "$(box_sdf blue_block   "0.04 0.04 0.04" "0 0 1"   $BLUE_MASS   $BLUE_MU)"   0.15 -0.03 $(echo "$TABLE_Z+0.03" | bc)
spawn yellow_block "$(box_sdf yellow_block "0.04 0.04 0.04" "1 0.9 0" $YELLOW_MASS $YELLOW_MU)" 0.09 -0.08 $(echo "$TABLE_Z+0.03" | bc)
echo "block friction: red=$RED_MU blue=$BLUE_MU yellow=$YELLOW_MU  mass: red=$RED_MASS blue=$BLUE_MASS yellow=$YELLOW_MASS"
# トレイ: 薄い板 (グリッパが触れても動かないよう重め。関節トルクでは押せない)
spawn blue_tray    "$(box_sdf blue_tray    "0.08 0.08 0.005" "0.2 0.4 1" 3.0)" 0.10  0.14 $(echo "$TABLE_Z+0.01" | bc)
spawn green_tray   "$(box_sdf green_tray   "0.08 0.08 0.005" "0.1 0.8 0.2" 3.0)" 0.17  0.10 $(echo "$TABLE_Z+0.01" | bc)
spawn red_tray     "$(box_sdf red_tray     "0.08 0.08 0.005" "1 0.45 0.45" 3.0)" 0.16 -0.11 $(echo "$TABLE_Z+0.01" | bc)
# planner の会話履歴を消す(新しいエピソード)。planner が居なければ 3 秒で諦める
timeout 3 ros2 topic pub --once -w 1 /planner/reset std_msgs/String "{data: 'world setup'}" >/dev/null 2>&1 || true
