#!/usr/bin/env bash
# コンテナ内で実行: Gazebo ウィンドウ(1280x720)を ffmpeg で録画する。
#   bash scripts/record.sh start demo1   -> ~/pai_work/pai-final-task/videos/demo1.mp4 に録画開始
#   bash scripts/record.sh stop          -> 停止
# ウィンドウ位置は xwininfo で自動取得(demo_gazebo.launch.py で起動した 1280x720 ウィンドウ前提)。
OUT_DIR=~/pai_work/pai-final-task/videos; mkdir -p "$OUT_DIR"
export DISPLAY=${DISPLAY:-:0}
case "$1" in
  start)
    # ウィンドウ位置: x はツリー表示の相対座標(枠込み)、y は絶対座標が実測で正しい
    line=$(xwininfo -root -tree | grep '"Gazebo": ("ign-gazebo-gui"')
    size=$(echo "$line" | grep -oE ' [0-9]+x[0-9]+\+' | head -1 | tr -d ' +')
    ax=$(echo "$line" | grep -oE '\+[0-9]+\+[0-9]+' | head -1 | cut -d+ -f2)
    ay=$(echo "$line" | grep -oE '\+[0-9]+\+[0-9]+' | tail -1 | cut -d+ -f3)
    # VNC はカーソルをフレームバッファに描くので、録画範囲外(画面右下)へ退避させる
    python3 - <<'PY'
from Xlib import display
from Xlib.ext import xtest
d = display.Display(); s = d.screen()
xtest.fake_input(d, 6, x=s.width_in_pixels - 2, y=s.height_in_pixels - 2); d.sync()
PY
    nohup ffmpeg -y -loglevel error -f x11grab -framerate 30 -video_size "$size" -i ":0.0+$ax,$ay" \
      -c:v libx264 -preset ultrafast -threads 2 -pix_fmt yuv420p "$OUT_DIR/${2:-demo}.mp4" > /tmp/ffmpeg.log 2>&1 &
    echo $! > /tmp/ffmpeg.pid; date +%s.%N > "$OUT_DIR/${2:-demo}.start"; echo "recording $size at +$ax,$ay -> $OUT_DIR/${2:-demo}.mp4" ;;
  stop)
    kill -INT "$(cat /tmp/ffmpeg.pid)" 2>/dev/null; sleep 2; echo "stopped"; ls -la "$OUT_DIR" ;;
  *) echo "usage: $0 start <name> | stop" ;;
esac
