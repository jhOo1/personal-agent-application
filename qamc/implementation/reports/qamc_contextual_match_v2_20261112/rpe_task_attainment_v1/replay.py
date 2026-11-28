"""Compare task-level attainment at every observed rational Match threshold."""
import json
from fractions import Fraction
from pathlib import Path

base = Path(__file__).resolve().parents[1]
rows = json.loads((base / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]
output = {}
for panel in ("common", "no_known_flags"):
    tasks = []
    for row in rows:
        cells = row["scores"]
        if not all(c["grade"].get("match") for c in cells.values()):
            continue
        if panel == "no_known_flags" and any(c["flags"] for c in cells.values()):
            continue
        fractions = {}
        for method, cell in cells.items():
            score = cell["grade"]["match"]
            assert score["positions"] == len(row["labels"]) and 0 <= score["matched"] <= score["positions"]
            fractions[method] = Fraction(score["matched"], score["positions"])
        tasks.append(fractions)
    thresholds = {v for task in tasks for v in task.values()} | {Fraction(1,2), Fraction(3,4), Fraction(9,10)}
    counts = {str(t): {method: sum(task[method] >= t for task in tasks) for method in tasks[0]}
              for t in sorted(thresholds)}
    output[panel] = {"tasks": len(tasks), "at_least": counts}
print(json.dumps(output, indent=2))
