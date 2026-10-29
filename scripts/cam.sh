#!/usr/bin/env bash
# コンテナ内で実行: GUIカメラを位置(x y z)から注視点(tx ty tz)へ向ける。例: bash scripts/cam.sh 0.5 -0.4 1.3 0.12 0.03 1.03
read -r X Y Z QX QY QZ QW <<< "$(python3 - "$@" <<'PY'
import sys, math
x,y,z,tx,ty,tz = map(float, sys.argv[1:7])
dx,dy,dz = tx-x, ty-y, tz-z
yaw = math.atan2(dy,dx); pitch = math.atan2(-dz, math.hypot(dx,dy))
cy,sy,cp,sp = math.cos(yaw/2),math.sin(yaw/2),math.cos(pitch/2),math.sin(pitch/2)
# q = qz(yaw)*qy(pitch)
print(x,y,z, -sy*sp, cy*sp, sy*cp, cy*cp)
PY
)"
ign service -s /gui/move_to/pose --reqtype ignition.msgs.GUICamera --reptype ignition.msgs.Boolean --timeout 2000 \
  --req "pose: {position: {x: $X, y: $Y, z: $Z}, orientation: {x: $QX, y: $QY, z: $QZ, w: $QW}}" >/dev/null
