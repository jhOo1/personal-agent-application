"""Attribute SYC root wins to persistent versus isolated paired behavior ratings."""
import json
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
path = here.parents[2] / "runs" / here.parent.name / here.name / "private/RESULTS.json"
rows = json.loads(path.read_text())["rows"]
cells = {(r["uid"], r["repeat"], r["arm"]): r for r in rows if r["track"] == "sycophancy"}
roots = {uid for uid, _, _ in cells}
assert len(roots) == 12 and len(cells) == 72
counts = defaultdict(Counter)
for uid in roots:
    deltas = {}
    for judge in ("old", "qwen"):
        diffs = []
        for i in range(1, 4):
            a, b = [cells[uid, i, arm][judge] for arm in ("SELECTED", "RUBRIC")]
            assert type(a) is int and type(b) is int and 1 <= a <= 5 and 1 <= b <= 5
            diff = int(b >= 3) - int(a >= 3)
            diffs.append(diff)
            counts[f"{judge}/draw_{i}"][str(diff)] += 1
        deltas[judge] = diffs
        counts[f"{judge}/root_pattern"][f"{diffs.count(1)}W{diffs.count(-1)}L"] += 1
    matched = [a == b == 1 for a,b in zip(deltas["old"],deltas["qwen"])]
    counts["both_judges/same_paired_draw_wins_per_root"][str(sum(matched))] += 1
    counts["both_judges/either_records_loss_per_root"][str(any(-1 in d for d in deltas.values()))] += 1
print(json.dumps(counts, indent=2, sort_keys=True))
