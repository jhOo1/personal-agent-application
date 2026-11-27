"""Export aggregate counts only, keeping draft texts and private grader traces local."""
import json
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2] / "runs" / here.parent.name
run = root / here.name
def read(p):
    return json.loads(p.read_text())

settled = read(run / "material/SETTLED.json")
old = {r["uid"]:r["score"] for r in read(root / "bench_gate_gepa_feedback_v1/material/SETTLED.json")["rows"] if r["arm"] == "baseline"}
diagnostics = Counter()
for uid in read(run / "material/EDITS.json"):
    before, after = old.get(uid), settled["new"].get(uid)
    if not before or not after:
        continue
    diagnostics["completeness_delta_" + str(after["task_completeness"] - before["task_completeness"])] += 1
    for a,b in zip(before["decisions"],after["decisions"],strict=True):
        assert (a["preference"], a["appropriate"]) == (b["preference"], b["appropriate"])
        if a["label"] != b["label"]:
            diagnostics["appropriate_flip" if a["appropriate"] else "inappropriate_flip"] += 1
            if "bold" in a["preference"].lower():
                diagnostics["bold_flip"] += 1
receipts = [read(p) for p in run.glob("Grade_*/visible/*/record.json")]
print(json.dumps(dict(**settled["summary"], diagnostics=diagnostics, requests=len(receipts),
                      statuses=Counter(r["status"] for r in receipts),
                      known_tokens=sum((r.get("usage") or {}).get("total_tokens") or 0 for r in receipts),
                      unknown_usage=sum((r.get("usage") or {}).get("total_tokens") is None for r in receipts),
                      retries=sum(r["automatic_retries"] for r in receipts)),indent=2))
