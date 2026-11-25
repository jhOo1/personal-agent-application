"""Measure exposed paired RPEval opportunities without using labels at inference."""
from collections import Counter
import json
from freeze_roster import RPE_ROUTES, archive

def audit(rows):
    counts = Counter()
    for row in rows:
        labels = row["labels"]
        if not labels:
            counts["unknown", "missing_labels"] += 1
            continue
        stratum = "contains_C" if "C" in labels else "B_only" if "B" in labels else "all_A"
        controls = row["controls"]
        task, history = (controls.get(key) or {} for key in ("TASK_ONLY", "RPR_PAPER_FULL"))
        cells = [(item.get("grade") or {}).get("match") for item in (task, history)]
        if not all(cells) or cells[0]["positions"] != cells[1]["positions"]:
            counts[stratum, "missing_pair"] += 1
            continue
        if task.get("flags") or history.get("flags"):
            counts[stratum, "flagged_pair"] += 1
            continue
        delta = cells[1]["matched"] - cells[0]["matched"]
        route = row["old_route"]
        counts[stratum, route, "history_better" if delta > 0 else "task_better" if delta < 0 else "tie"] += 1
    return counts

if __name__ == "__main__":
    print(json.dumps({" / ".join(key): value for key, value in
                      sorted(audit(archive.read(RPE_ROUTES)["rows"]).items())}, indent=2))
