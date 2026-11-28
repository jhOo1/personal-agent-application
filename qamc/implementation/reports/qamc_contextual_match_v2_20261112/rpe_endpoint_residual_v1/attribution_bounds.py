"""Sharp per-class bounds conditional only on reported Match and author labels."""
from collections import Counter
import json
from pathlib import Path

archive = Path(__file__).resolve().parent.parent / "ipe_c_two_endpoint_completion_v1/RESULTS.json"
groups = {"all": [], "no recorded flag": []}
for r in json.loads(archive.read_text())["rows"]:
    labels = r["labels"]
    if not labels or "C" not in labels:
        continue
    cells = [(r["scores"].get(k) or {}) for k in ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")]
    match = [(s.get("grade") or {}).get("match") for s in cells]
    if not all(m and m["positions"] == len(labels) and type(m["matched"]) is int
               and 0 <= m["matched"] <= len(labels) for m in match):
        continue
    deficits = [len(labels)-m["matched"] for m in match]
    row = labels, deficits[0], min(deficits[1:])
    groups["all"].append(row)
    if all(not s["flags"] for s in cells):
        groups["no recorded flag"].append(row)

print("# Which class must contain a mismatch?\n")
print("|Panel (C-bearing tasks)|Endpoint|Class|Positions|Mismatch range|Tasks forced to miss at least one|Tasks where a miss is possible|")
print("|---|---|---|---:|---:|---:|---:|")
for scope, rows in groups.items():
    assert len(rows) == (110 if scope == "all" else 67)
    for index, name in enumerate(("IPE-C","better saved score"), start=1):
        for label in "ABC":
            totals = Counter()
            for row in rows:
                labels, deficit = row[0], row[index]
                n, k = len(labels), labels.count(label)
                low, high = max(0,deficit-(n-k)), min(k,deficit)
                totals.update(positions=k, low=low, high=high, forced=int(low>0), possible=int(high>0))
            print(f"|{scope}|{name}|{label}|{totals['positions']}|{totals['low']}–{totals['high']}|{totals['forced']}|{totals['possible']}|")
