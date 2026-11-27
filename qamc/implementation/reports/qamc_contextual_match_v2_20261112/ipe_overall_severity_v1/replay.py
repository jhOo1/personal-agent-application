"""Jointly valid whole-answer severity and position Match, with unchanged endpoints."""
from collections import Counter, defaultdict
from pathlib import Path
import json

here = Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())

def summarize(rows):
    total = defaultdict(Counter)
    transitions = defaultdict(Counter)
    kept = 0
    for cells in rows:
        if any(not g.get("match") or type(g.get("Judge")) is not int or not 0 <= g["Judge"] <= 5 for g in cells.values()):
            continue
        assert len({g["match"]["positions"] for g in cells.values()}) == 1
        kept += 1
        for arm,g in cells.items():
            total[arm].update(severity=g["Judge"], matched=g["match"]["matched"], positions=g["match"]["positions"])
        for arm in ("empty","full"):
            a,b=cells["IPE"],cells[arm]
            differences=(a["match"]["matched"]-b["match"]["matched"], b["Judge"]-a["Judge"])
            signs=tuple("win" if d>0 else "loss" if d<0 else "tie" for d in differences)
            transitions[arm]["/".join(signs)] += 1
    return dict(allocated=len(rows), common=kept, total=total, match_and_severity=transitions)

arch=read(here.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
report={"archive":summarize([{name:r["scores"][key]["grade"] for name,key in
                              (("IPE","IPE_C"),("empty","TASK_ONLY"),("full","RPR_PAPER_FULL"))} for r in arch])}
runs=here.parents[2]/"runs"/here.parent.name/"rpe_ipe_fresh_repeat_v1"
for i in (1,2):
    rows=read(runs/f"deployment{i}/RESULTS.json")["rows"]
    report[f"fresh{i}"]=summarize([{name:(r["scores"].get(key) or {}).get("grade",{}) for name,key in
                                   (("IPE",r["branch"]),("empty","TASK_ONLY"),("full","RP_FULL"))} for r in rows])
print(json.dumps(report,indent=2))
