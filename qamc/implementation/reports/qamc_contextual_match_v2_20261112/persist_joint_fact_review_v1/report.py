"""Publish case-level scores and source IDs without releasing private model traces."""
from collections import Counter
import json
from pathlib import Path

here = Path(__file__).resolve().parent
data = json.loads((here.parents[2] / "runs" / here.parent.name / here.name / "private/SETTLED.json").read_text())
assert len({(r["uid"],r["arm"]) for r in data["rows"]}) == 8
print("# Joint fact review on four exposed diagnostic tasks\n")
print("Counts and index lists below refer to the frozen original order (zero based). For utility a pass requires rating 3. For risk ratings 1 and 2 pass. The two graders are local adaptations.\n")
print("| Case | Arm | Added source IDs | Actor | GPT | Qwen |")
print("|---|---|---|---|---:|---:|")
for r in sorted(data["rows"],key=lambda x:(x["uid"],x["arm"])):
    fields=[r["uid"].split("/")[-1][:8],r["arm"],r["add"],r["origin"],r["GPT"],r["Qwen"]]
    print("| "+" | ".join("UNKNOWN" if v is None else str(v) for v in fields)+" |")
ledger=data["ledger"]
print("\nPhysical requests by stage:",dict(Counter(r["unit"]["stage"] for r in ledger)))
print("\nRequest status:",dict(Counter(r["status"] for r in ledger)))
print("\nReported tokens:",sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger))
print("\nUnknown usage:",sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger))
print("\nAutomatic retries:",sum(r["automatic_retries"] for r in ledger))
