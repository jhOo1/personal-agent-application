"""Replay a query-only binary policy on registered endpoint receipts; output aggregates."""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
archive = HERE.parents[2] / "runs" / HERE.parent.name / "persist_exposure_fr3_v1" / "RESULTS.json"
rows = json.loads(archive.read_text())["rows"]
groups = defaultdict(lambda: defaultdict(dict))
for row in rows:
    branch = (row["exposure"] or {}).get("branch")
    assert branch in (None, "grounding", "style")
    if branch is None:
        assert row["route"]["status"] != "OK"
    else:
        assert row["route"]["status"] == "OK"
        raw = json.loads(row["route"]["answer"])
        assert raw["check_history"] is (branch == "style")
    route = {"style": "FULL", "grounding": "EMPTY"}.get(branch)
    for name in ["QUERY_BINARY", "FULL", "EMPTY", "SELECTED", "GROUP", "RUBRIC"]:
        endpoint = route if name == "QUERY_BINARY" else name
        score = row["methods"][endpoint]["score"] if endpoint else None
        draws = groups[row["track"]][row["uid"]].setdefault(name, {})
        assert row["repeat"] not in draws
        draws[row["repeat"]] = score["rating"] if score else None

result = {}
for track, cases in groups.items():
    counts = defaultdict(Counter)
    paired = defaultdict(Counter)
    for cells in cases.values():
        outcomes = {}
        for name, draws in cells.items():
            ratings = list(draws.values())
            if track == "beneficial_memory_usage":
                assert len(draws) == 1
                passed = None if ratings[0] is None else ratings[0] == 3
            else:
                assert set(draws) == {1, 2, 3}
                passed = False if any(r is not None and r >= 3 for r in ratings) else None if None in ratings else True
            outcomes[name] = passed
            counts[name][{True:"pass",False:"fail",None:"unknown"}[passed]] += 1
        for name, control in outcomes.items():
            q = outcomes["QUERY_BINARY"]
            key = "unknown" if None in (q,control) else "tie" if q == control else "win" if q else "loss"
            paired[name][key] += 1
    result[track] = {"outcomes":counts, "paired_query_vs_control":paired}
assert sum(len(cases) for cases in groups.values()) == 49 and len(rows) == 111
print(json.dumps(result, indent=2, sort_keys=True))
