#!/usr/bin/env python3
"""コンテナ内で実行: 4本のデモ録画から提出用動画(1〜3分)を組み立てる。
   python3 scripts/make_final.py  -> videos/final.mp4
 構成: タイトル+構成図 → ①基本 → ②曖昧指示 → ③仕分け → ④妨害復帰 → 工夫点と今後
 各デモは annotate.sh の 2倍速・字幕入り版を使い、LLM の計画待ち区間(数秒を残して)をカットする。"""
import os, subprocess, sys
from weasyprint import HTML

ROOT = os.path.expanduser("~/pai_work/pai-final-task")
V = os.path.join(ROOT, "videos"); W = os.path.join(V, "_final"); os.makedirs(W, exist_ok=True)
DEMOS = [  # (name, 見出し, 説明, 再生速度)  ※3分以内に収めるため長いデモは 2.5 倍速(画面に表記)
    ("basic", "① 基本のピック&プレース", "物体名で指示 → LLM が手順を生成 → IK で実行 → monitor が配置を確認", 2),
    ("ambiguous", "② 曖昧な指示の解釈", "「同じ色のトレイ」を物体一覧から LLM が解釈する", 2),
    ("sort", "③ 複数物体の仕分け", "色ごとに対応するトレイへ。対応するトレイが無い黄色は残すと判断", 2.5),
    ("recover", "④ 妨害からの回復（閉ループ再計画）", "把持直後にブロックを動かす → 置き位置に物体なし → 失敗理由付きで再計画", 2.5),
]

def run(*cmd): subprocess.run(cmd, check=True)
def dur(path): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]))

CSS = """<style>
@page { size: 1280px 720px; margin: 0; }
body { margin: 0; width: 1280px; height: 720px; font-family: 'Noto Sans CJK JP', sans-serif; color: #eee; background: #1b1f24; }
.card { box-sizing: border-box; width: 1280px; height: 720px; padding: 56px 72px; }
h1 { font-size: 44px; margin: 0 0 10px; color: #fff; line-height: 1.3; }
h2 { font-size: 30px; margin: 0 0 24px; color: #9be; font-weight: normal; }
.num { font-size: 52px; color: #fff; margin: 160px 0 20px; }
.desc { font-size: 30px; color: #ccc; }
.instr { font-size: 34px; color: #ffd166; margin-top: 36px; }
ul { font-size: 27px; line-height: 1.55; margin: 0; padding-left: 1.2em; }
table.cols { width: 100%; border-collapse: collapse; margin-top: 10px; }
table.cols td { width: 50%; vertical-align: top; padding: 0 30px 0 0; }
h3 { font-size: 30px; color: #9be; margin: 0 0 10px; }
.small { font-size: 22px; color: #999; margin-top: 30px; }
img { width: 1120px; display: block; margin: 8px auto 0; background: #fff; border-radius: 10px; padding: 8px; }
</style>"""

def card(name, html, seconds):
    pdf = os.path.join(W, f"{name}.pdf"); png = os.path.join(W, name)
    HTML(string=f"<html><head><meta charset='utf-8'>{CSS}</head><body><div class='card'>{html}</div></body></html>",
         base_url=os.path.join(ROOT, "docs") + "/").write_pdf(pdf)
    run("pdftoppm", "-r", "96", "-f", "1", "-l", "1", "-png", "-singlefile", pdf, png)
    out = os.path.join(W, f"{name}.mp4")
    run("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", png + ".png", "-t", str(seconds),
        "-vf", "scale=1280:720,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out)
    return out

def demo_clip(name, SPEED):
    """倍速字幕版を作り、計画待ち区間(直前のイベントから2.5秒残す)をカットする。"""
    subprocess.run(["bash", os.path.join(ROOT, "scripts/annotate.sh"), name, f"{SPEED:g}"], check=True, stdout=subprocess.DEVNULL)
    src = os.path.join(V, f"{name}_sub{SPEED:g}x.mp4")
    t0 = float(open(os.path.join(V, f"{name}.start")).read())
    ev = [l.rstrip("\n").split("\t") for l in open(os.path.join(V, f"{name}.events"), encoding="utf-8")]
    ev = [(float(t) - t0, k) for t, k, *_ in ev]
    total = dur(src)
    t_instr = next(t for t, k in ev if k == "instruction")
    t_result = next((t for t, k in ev if k == "result"), total * SPEED)
    cuts, prev = [], None
    for t, k in ev:
        if k in ("instruction", "replan"): prev = t
        elif k == "plan" and prev is not None:
            a, b = prev + 2.5, t - 1.0
            if b > a: cuts.append((a, b))
            prev = None
    keep, cur, end = [], max(0.0, t_instr - 1.0), min(total * SPEED, t_result + 2.0)
    for a, b in cuts:
        keep.append((cur, a)); cur = b
    keep.append((cur, end))
    parts = "".join(f"[0:v]trim=start={a/SPEED:.2f}:end={b/SPEED:.2f},setpts=PTS-STARTPTS[v{i}];" for i, (a, b) in enumerate(keep))
    concat = "".join(f"[v{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=0[out]"
    out = os.path.join(W, f"{name}_cut.mp4")
    run("ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex", parts + concat, "-map", "[out]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", out)
    print(f"{name}: keep {[(round(a,1), round(b,1)) for a, b in keep]} -> {dur(out):.1f}s")
    return out

pieces = []
pieces.append(card("title", """
<h1>自然言語指示によるロボットアームのピック&プレース</h1>
<h2>LLM プランナー ＋ 閉ループ再計画（CRANE+ V2, ROS 2 Humble, Ignition Gazebo）</h2>
<img src="img/architecture.svg">
<div class="small">LLM (Claude) は指示をサブゴール列に翻訳するだけ。運動は解析 IK、失敗の検知と再計画要求は monitor が担当。
物体位置は俯瞰カメラ画像の色分割から推定（シミュレータの真値は不使用、右下の小窓）。動画の実行区間は 2〜2.5 倍速（画面右上に表示）。</div>""", 8))
for name, title, desc, speed in DEMOS:
    pieces.append(card(f"sec_{name}", f"<div class='num'>{title}</div><div class='desc'>{desc}</div>", 2.5))
    pieces.append(demo_clip(name, speed))
pieces.append(card("closing", """
<h1>工夫した点と今後の発展</h1>
<table class="cols"><tr><td><h3>工夫した点</h3><ul>
<li>LLM を制御ループの外に置くイベント駆動設計（遅延の影響なし）</li>
<li>JSON Schema の固定語彙＋到達範囲チェックの二重の安全層</li>
<li>monitor の失敗理由をそのまま LLM に渡す自然言語の再計画ループ</li>
<li>カメラ画像の色分割＋逆投影による知覚（真値不使用, 誤差 2 mm）</li>
<li>4 デモ×5 回の無人評価で失敗要因を特定し成功率を改善</li></ul></td>
<td><h3>今後の発展</h3><ul>
<li>VLM による知覚で未知物体の指示へ一般化</li>
<li>世界モデル＋MPC による controller の置き換え</li>
<li>toio（押し運び）への同一アーキテクチャの移植</li>
<li>実行中の物体追跡で完了を待たずに再計画</li></ul></td></tr></table>""", 9))

lst = os.path.join(W, "list.txt")
open(lst, "w").write("".join(f"file '{p}'\n" for p in pieces))
final = os.path.join(V, "final.mp4")
run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", final)
print(f"final: {dur(final):.1f}s -> {final}")
