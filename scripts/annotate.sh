#!/usr/bin/env bash
# コンテナ内で実行: 録画 videos/<name>.mp4 に、events ログを元に指示文と状態の字幕を焼き込む。
#   bash scripts/annotate.sh <name> [speed]   -> videos/<name>_sub.mp4 (speed=2 なら videos/<name>_sub2x.mp4 に2倍速・「2倍速」表記付き)
set -e
cd ~/pai_work/pai-final-task/videos
NAME=$1; SPEED=${2:-1}
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
T0=$(cat "$NAME.start"); OUT="${NAME}_sub.mp4"; [ "$SPEED" != 1 ] && OUT="${NAME}_sub${SPEED}x.mp4"
python3 - "$NAME" "$T0" "$SPEED" "$FONT" > "/tmp/${NAME}_filter.txt" <<'PY'
import sys, os
name, t0, speed, font = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
ev = [l.rstrip("\n").split("\t", 2) for l in open(f"{name}.events", encoding="utf-8")]
ev = [(float(t) - t0, k, (x[0] if (x := rest) else "")) for t, k, *rest in ev]
tmp = f"/tmp/{name}_txt"; os.makedirs(tmp, exist_ok=True)
items = []   # (start, end, text, style)
instr = next((x for _, k, x in ev if k == "instruction"), "")
t_instr = next((t for t, k, _ in ev if k == "instruction"), 0.0)
END = 1e6
items.append((t_instr, END, f"指示: 「{instr}」", "top"))
status = []  # (t, text)
for t, k, x in ev:
    if k == "instruction": status.append((t, "LLM (Claude) が計画を生成中…"))
    elif k == "plan": status.append((t, f"計画を受理 ({x}) → 実行中"))
    elif k == "demo": status.append((t, x))
    elif k == "replan": status.append((t, "monitor: 置き位置に物体なし → 再計画を要求"))
    elif k == "result":
        ok = x.startswith("success")
        status.append((t, "monitor: 配置を確認 → タスク完了" if ok else "monitor: 失敗 " + x[8:60]))
for i, (t, text) in enumerate(status):
    end = status[i + 1][0] if i + 1 < len(status) else END
    items.append((t, end, text, "bottom"))
# 妨害・再計画は短く強調して出す(次の状態に上書きされるまで)
out = []
for i, (s, e, text, style) in enumerate(items):
    p = f"{tmp}/{i}.txt"; open(p, "w", encoding="utf-8").write(text)
    s, e = s / speed, e / speed
    if style == "top":
        out.append(f"drawtext=fontfile={font}:textfile={p}:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=12:x=20:y=60:enable='between(t,{s:.2f},{e:.2f})'")
    else:
        col = "yellow" if ("妨害" in text or "再計画" in text) else ("#7CFC00" if "完了" in text else "white")
        out.append(f"drawtext=fontfile={font}:textfile={p}:fontsize=30:fontcolor={col}:box=1:boxcolor=black@0.55:boxborderw=10:x=100:y=h-70:enable='between(t,{s:.2f},{e:.2f})'")
if speed != 1:
    p = f"{tmp}/speed.txt"; open(p, "w").write(f"{speed:g}倍速")
    out.append(f"drawtext=fontfile={font}:textfile={p}:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=8:x=w-tw-20:y=60")
vf = ",".join(out)
if speed != 1: vf = f"setpts=PTS/{speed}," + vf
print(vf)
PY
ffmpeg -y -loglevel error -i "$NAME.mp4" -filter_complex_script "/tmp/${NAME}_filter.txt" -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$OUT"
echo "wrote videos/$OUT"
