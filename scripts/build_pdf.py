#!/usr/bin/env python3
"""コンテナ内で実行: docs/report.md を日本語フォント付き PDF に変換する。
   python3 scripts/build_pdf.py [出力パス]   (既定: docs/report.pdf)"""
import sys, os, markdown
from weasyprint import HTML, CSS

root = os.path.expanduser("~/pai_work/pai-final-task")
src = os.path.join(root, "docs", "report.md")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "docs", "report.pdf")
md = open(src, encoding="utf-8").read()
body = markdown.markdown(md, extensions=["tables", "fenced_code"])
css = CSS(string="""
@page { size: A4; margin: 20mm 18mm; @bottom-center { content: counter(page) " / " counter(pages); font-size: 9pt; color: #666; } }
body { font-family: "Noto Sans CJK JP", sans-serif; font-size: 10.5pt; line-height: 1.6; color: #222; }
h1 { font-size: 18pt; border-bottom: 2px solid #444; padding-bottom: 4px; margin-top: 0; }
h2 { font-size: 14pt; margin-top: 18pt; border-left: 5px solid #2a6; padding-left: 8px; }
h3 { font-size: 11.5pt; margin-top: 12pt; }
p, li { text-align: justify; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9.5pt; }
th, td { border: 1px solid #999; padding: 4px 6px; vertical-align: top; }
th { background: #eef3ee; }
pre { background: #f4f4f4; border: 1px solid #ddd; padding: 8px; font-size: 8.5pt; line-height: 1.3; white-space: pre; overflow: hidden; font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", monospace; }
code { font-family: "Noto Sans Mono CJK JP", "Noto Sans CJK JP", monospace; font-size: 9pt; background: #f4f4f4; padding: 0 2px; }
pre code { background: none; padding: 0; }
ul, ol { padding-left: 1.5em; }
img { max-width: 100%; display: block; margin: 6pt auto; }
p > img + em, p:has(img) { text-align: center; }
""")
HTML(string=f"<html><head><meta charset='utf-8'></head><body>{body}</body></html>", base_url=os.path.join(root, "docs") + "/").write_pdf(out, stylesheets=[css])
print("wrote", out)

