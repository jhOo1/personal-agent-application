"""Count how many unresolved external roots must fail for a strict pass-count win."""
import json
from collections import defaultdict
from pathlib import Path

report = Path(__file__).resolve().parent
inputs = report.parents[2] / "runs" / report.parent.name / report.name / "private"
rows = defaultdict(dict)
for draw in (1, 2, 3):
    for row in json.loads((inputs / f"DRAW_{draw}.json").read_text())["rows"]:
        key = (row["track"], row["arm"], row["uid"])
        assert row["draw"] == draw and draw not in rows[key]
        rows[key][draw] = row

for judge in ("GPT", "Qwen"):
    tracks = defaultdict(lambda: defaultdict(list))
    for (track, arm, uid), draws in rows.items():
        utility = track == "beneficial_memory_usage"
        assert set(draws) == ({1} if utility else {1, 2, 3})
        grades = [row[judge] for row in draws.values()]
        passed = [(v == 3 if utility else v < 3) for v in grades if v is not None]
        state = "fail" if False in passed else "pass" if len(passed) == len(grades) else "unknown"
        tracks[track][arm].append((uid, state))
    for track, arms in tracks.items():
        external = dict(arms["MEMADAPTER"])
        possible = sum(v != "fail" for v in external.values())
        unknown = sum(v == "unknown" for v in external.values())
        for arm in ("SELECTED", "BREADTH"):
            internal = dict(arms[arm])
            assert internal.keys() == external.keys()
            floor = sum(v == "pass" for v in internal.values())
            ceiling = sum(v != "fail" for v in internal.values())
            # Strict lead when external passes fall below the internal count.
            print(judge, track, arm, "external unresolved", unknown,
                  "external failures needed (internal missing all pass / all fail)",
                  max(0, possible - ceiling + 1), max(0, possible - floor + 1))
