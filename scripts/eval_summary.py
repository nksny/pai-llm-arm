#!/usr/bin/env python3
"""logs/eval.jsonl を集計して Markdown 表を出す。  python3 scripts/eval_summary.py [tag]"""
import json, statistics as st, sys
from collections import defaultdict
tag = sys.argv[1] if len(sys.argv) > 1 else None
rows = [json.loads(l) for l in open("logs/eval.jsonl", encoding="utf-8") if l.strip()]
if tag:
    rows = [r for r in rows if r["tag"] == tag]
by = defaultdict(list)
for r in rows:
    by[r["name"]].append(r)
order = ["basic", "ambiguous", "sort", "recover"]
print("| デモ | 試行 | 成功 | 成功率 | 所要時間 平均(最小–最大) [s] | 再計画 平均 | LLM呼出 平均 | 計画時間 平均 [s] | 入力/出力トークン 平均 |")
print("|---|---|---|---|---|---|---|---|---|")
for n in order + [k for k in by if k not in order]:
    rs = by.get(n)
    if not rs:
        continue
    ok = sum(r["success"] for r in rs); d = [r["duration_s"] for r in rs]
    pt = [x for r in rs for x in r["plan_time_s"]]
    print(f"| {n} | {len(rs)} | {ok} | {100*ok/len(rs):.0f}% | {st.mean(d):.0f} ({min(d):.0f}–{max(d):.0f}) | "
          f"{st.mean([r['replans'] for r in rs]):.1f} | {st.mean([r['llm_calls'] for r in rs]):.1f} | "
          f"{st.mean(pt) if pt else 0:.1f} | {st.mean([r['in_tokens']/max(r['llm_calls'],1) for r in rs]):.0f} / "
          f"{st.mean([r['out_tokens']/max(r['llm_calls'],1) for r in rs]):.0f} |")
tot = len(rows); ok = sum(r["success"] for r in rows)
print(f"\n合計 {tot} 試行, 成功 {ok} ({100*ok/max(tot,1):.0f}%)")
fails = [r for r in rows if not r["success"]]
if fails:
    print("\n失敗一覧:")
    for r in fails:
        print(f"- {r['name']}: {r['result'][:80]}")
