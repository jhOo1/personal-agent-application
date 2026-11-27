"""Paired transitions to/from perfect position Match against the no-history endpoint."""
import json
from collections import Counter, defaultdict
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json"
rows = json.loads(source.read_text())["rows"]
tables = defaultdict(Counter)
for row in rows:
    cells = row["scores"]
    if not all(cell["grade"].get("match") for cell in cells.values()):
        continue
    labels = row["labels"]
    group = "contains_C" if "C" in labels else "contains_B_no_C" if "B" in labels else "all_A"
    task, ipe = [cells[k]["grade"]["match"] for k in ("TASK_ONLY", "IPE_C")]
    assert task["positions"] == ipe["positions"] == len(labels)
    old, new = task["matched"], ipe["matched"]
    state = ("exact" if old == len(labels) else "partial") + "_to_" + ("exact" if new == len(labels) else "partial")
    for split in ["all"] + (["no_flags"] if all(c["flags"] == [] for c in cells.values()) else []):
        counts = tables[split + "/" + group]
        counts["tasks"] += 1
        for arm, cell in cells.items():
            grade = cell["grade"]
            if grade["match"]["matched"] == len(labels):
                counts[arm + "_exact_from_positions"] += 1
            if grade.get("full_match") == 1:
                counts[arm + "_reported_full_match"] += 1
        counts[f"ipe_unmatched_{len(labels) - new}"] += 1
        counts[state] += 1
        counts[state + "_match_delta"] += new - old
print(json.dumps(tables, indent=2, sort_keys=True))
