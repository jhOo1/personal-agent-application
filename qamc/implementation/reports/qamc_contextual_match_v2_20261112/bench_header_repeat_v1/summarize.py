"""Report repeatability by wire and paired edit effects; case indices contain no raw text."""
import json
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
run = here.parents[2]/"runs"/here.parent.name/here.name
rows = json.loads((run/"material/SETTLED.json").read_text())["rows"]
pairs = defaultdict(dict)
for row in rows:
    pairs[row["field"],row["case"]][row["arm"]] = row
stats = defaultdict(Counter)
details = []
for (field,case),arms in sorted(pairs.items()):
    assert set(arms) == {"baseline","edit"}
    kind = "completeness" if field == "BenchComplete" else "brevity"
    t = stats[kind]
    def numeric(v):
        return v if kind == "completeness" else int(v=="follow")
    for row in arms.values():
        if row["replicate"] is not None:
            t["valid_wires"] += 1
            t["within_wire_changes"] += row["original"] != row["replicate"]
    if any(row["replicate"] is None for row in arms.values()):
        t["missing_pairs"]+=1
        continue
    t["complete_pairs"]+=1
    changes={}
    for draw in ("original","replicate"):
        diff=numeric(arms["edit"][draw])-numeric(arms["baseline"][draw])
        changes[draw]=diff
        t[draw+"_net_edit"]+=diff
    t["identical_pair_difference"] += changes["original"]==changes["replicate"]
    details.append(dict(case=case,kind=kind,**changes))
receipts=[json.loads(p.read_text()) for p in run.glob("Repeat_*/visible/*/record.json")]
assert len(receipts)==len(rows)
print(json.dumps(dict(stats=stats,paired_changes=details,requests=len(receipts),
    transport=Counter(r["status"] for r in receipts),
    tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in receipts),
    unknown_usage=sum((r.get("usage") or {}).get("total_tokens") is None for r in receipts),
    retries=sum(r["automatic_retries"] for r in receipts)),indent=2))
