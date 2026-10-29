#!/usr/bin/env python3
"""eval_batch.sh から呼ばれる: 1試行の結果を JSON 1行で出力する。
   引数: tag name instruction t0 t1 result_file llm_lines0 monitor_lines0 planner_lines0"""
import json, re, sys, time
tag, name, instr, t0, t1, resf, llm0, mon0, pln0 = sys.argv[1:10]
t0, t1 = float(t0), float(t1)
try:
    res = open(resf, encoding="utf-8").read()
except Exception:
    res = ""
m = re.search(r"data: '(.*)'", res, re.S)
result = m.group(1).strip() if m else "timeout"
llm = [json.loads(l) for l in open("logs/llm.jsonl", encoding="utf-8").read().splitlines()[int(llm0):] if l.strip()]
mon = open("/tmp/monitor.log", encoding="utf-8", errors="replace").read().splitlines()[int(mon0):]
pln = open("/tmp/planner.log", encoding="utf-8", errors="replace").read().splitlines()[int(pln0):]
plan_t = [float(x) for x in re.findall(r"plan \(([\d.]+)s", "\n".join(pln))]
rec = {
    "t": time.time(), "tag": tag, "name": name, "instruction": instr,
    "success": result.startswith("success"), "result": result,
    "duration_s": round(t1 - t0, 1),
    "replans": sum(1 for l in mon if "replan #" in l and "requested" in l),
    "llm_calls": len(llm),
    "plan_time_s": [round(x, 1) for x in plan_t],
    "in_tokens": sum(r.get("in_tokens") or 0 for r in llm),
    "out_tokens": sum(r.get("out_tokens") or 0 for r in llm),
    "steps": [len(json.loads(r["response"]).get("subgoals", [])) for r in llm],
    "placements": sum(1 for l in mon if "reached by" in l),
}
print(json.dumps(rec, ensure_ascii=False))
