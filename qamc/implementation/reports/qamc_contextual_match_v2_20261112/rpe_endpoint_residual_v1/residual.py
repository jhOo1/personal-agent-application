"""Count the residual mismatch of the better archived exposure endpoint by task."""
from collections import Counter, defaultdict
import json
from pathlib import Path

base = Path(__file__).resolve().parent.parent
rows = json.loads((base / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]
methods = ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")
summary = defaultdict(Counter)
groups = defaultdict(set)
for row in rows:
    scores = row["scores"]
    if not all((scores.get(k) or {}).get("grade", {}).get("match") for k in methods):
        continue
    n = len(row["labels"])
    grades = [scores[k]["grade"]["match"] for k in methods]
    if not all(g["positions"] == n and type(g["matched"]) is int and 0 <= g["matched"] <= n for g in grades):
        continue
    route, empty, full = (n-g["matched"] for g in grades)
    residual = min(empty, full)
    assert route in (empty, full)
    label = "contains C" if "C" in row["labels"] else "only A" if set(row["labels"]) == {"A"} else "B without C"
    clean = all(not scores[k]["flags"] for k in methods)
    for part in ["all", label] + (["no flags", label+" (no flags)"] if clean else []):
        s = summary[part]
        s.update(tasks=1, ipe_exact=int(route==0), oracle_exact=int(residual==0),
                 one=int(residual==1), two=int(residual==2), three_plus=int(residual>=3),
                 missed=route, residual=residual)
        if residual >= 2:
            groups[part].add(row["source_group"])
assert len(rows)==300 and summary["all"]["tasks"]==274 and summary["no flags"]["tasks"]==184
assert summary["all"]["ipe_exact"]==95 and summary["all"]["oracle_exact"]==111
print("# Minimum mismatch after choosing the better of the two saved answers\n")
print("Tasks are exposed development cases. Joint Match is derived from matched positions. Oracle choice uses scores after generation.\n")
print("|Subset|Tasks|IPE-C exact|Oracle exact|1 mismatch|2 mismatches|3+ mismatches|Groups with 2+|IPE-C missed positions|Oracle missed positions|")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for part in ("all","only A","B without C","contains C","no flags","only A (no flags)","B without C (no flags)","contains C (no flags)"):
    s=summary[part]
    assert s["tasks"]==sum(s[k] for k in ("oracle_exact","one","two","three_plus"))
    print("|"+"|".join(map(str,[part,*[s[k] for k in ("tasks","ipe_exact","oracle_exact","one","two","three_plus")],
                                len(groups[part]),s["missed"],s["residual"]]))+"|")
