#!/usr/bin/env bash
# デモ用ワールド整備: 既存の木ブロックを消し、色付きブロックとトレイを配置する。
# コンテナ内で、crane_plus_gazebo の launch 起動後に実行する。
# 座標は世界座標。テーブル面は z=1.015 (= ロボット base_link の高さ)
set -e
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash
WORLD=default
TABLE_Z=1.015

# 既存の木ブロックと、再実行時の旧デモ物体を消す
for m in wood_cube_5cm red_block blue_block yellow_block blue_tray green_tray red_tray; do
  ign service -s /world/$WORLD/remove --reqtype ignition.msgs.Entity --reptype ignition.msgs.Boolean \
    --timeout 2000 --req "name: \"$m\" type: MODEL" >/dev/null 2>&1 || true
done
sleep 1

box_sdf() {  # name size_xyz rgb mass
  cat <<SDF
<?xml version="1.0"?><sdf version="1.6"><model name="$1"><link name="link">
<inertial><mass>$4</mass><inertia><ixx>1e-5</ixx><iyy>1e-5</iyy><izz>1e-5</izz></inertia></inertial>
<collision name="c"><geometry><box><size>$2</size></box></geometry>
<surface><friction><ode><mu>1.2</mu><mu2>1.2</mu2></ode></friction></surface></collision>
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
spawn red_block    "$(box_sdf red_block    "0.04 0.04 0.04" "1 0 0"   0.02)" 0.10  0.05 $(echo "$TABLE_Z+0.03" | bc)
spawn blue_block   "$(box_sdf blue_block   "0.04 0.04 0.04" "0 0 1"   0.02)" 0.15 -0.03 $(echo "$TABLE_Z+0.03" | bc)
spawn yellow_block "$(box_sdf yellow_block "0.04 0.04 0.04" "1 0.9 0" 0.02)" 0.09 -0.08 $(echo "$TABLE_Z+0.03" | bc)
# トレイ: 薄い板 (グリッパが触れても動かないよう重め。関節トルクでは押せない)
spawn blue_tray    "$(box_sdf blue_tray    "0.08 0.08 0.005" "0.2 0.4 1" 3.0)" 0.10  0.14 $(echo "$TABLE_Z+0.01" | bc)
spawn green_tray   "$(box_sdf green_tray   "0.08 0.08 0.005" "0.1 0.8 0.2" 3.0)" 0.17  0.10 $(echo "$TABLE_Z+0.01" | bc)
spawn red_tray     "$(box_sdf red_tray     "0.08 0.08 0.005" "1 0.45 0.45" 3.0)" 0.16 -0.11 $(echo "$TABLE_Z+0.01" | bc)
