"""Compare existing strict utility grades on the same sources in two deployments."""
import json
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
runs = here.parents[2] / "runs" / here.parent.name
paths = [
    runs / "persist_utility_fresh_deployment_v1/private/SETTLED.json",
    runs / "persist_memadapter_release_v1/private/DRAW_1.json",
]


def selected_rows(path):
    rows = {}
    for row in json.loads(path.read_text())["rows"]:
        if row["arm"] == "SELECTED" and row.get("track", "beneficial_memory_usage") == "beneficial_memory_usage":
            assert row["uid"] not in rows
            rows[row["uid"]] = row
    return rows


def outcome(value):
    if value is None:
        return "unknown"
    assert value in (1, 2, 3)
    return "pass" if value == 3 else "fail"


first, second = map(selected_rows, paths)
assert len(first) == 18 and len(second) == 20 and first.keys() <= second.keys()
for judge in ("GPT", "Qwen"):
    pairs = Counter((outcome(first[u][judge]), outcome(second[u][judge])) for u in first)
    print(judge, sorted(pairs.items()))
