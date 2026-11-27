"""Joint final-answer success on archived BenchPreS task-only, RP, and Gate answers."""
from pathlib import Path
from collections import Counter
import json

base = Path(__file__).resolve().parent.parent
rows = json.loads((base / "paired_regret_policy_v1/MATRIX.json").read_text())["rows"]
cases = [r for r in rows if r["domain"] == "BenchPreS"]
report = {}
for required_completeness in (5, 4):
    counts = Counter()
    profiles = set()
    winning_groups = set()
    contrasts = Counter()
    for r in cases:
        cells = r["metrics"]
        if not all(cells[a] is not None for a in ("G","T","H")):
            counts["missing_triple"] += 1
            continue
        counts["comparable"] += 1
        profiles.add(r["group"])
        success = {}
        for arm, cell in cells.items():
            assert r["answers"][arm] and 0 <= cell["primary"] <= r["denom"] and cell["MR"] <= 0
            success[arm] = cell["primary"] == r["denom"] and cell["MR"] == 0 and cell["completeness"] >= required_completeness
            counts[arm+"_passes"] += success[arm]
        if success["G"] and not success["T"] and not success["H"]:
            winning_groups.add(r["group"])
            counts["gate_only"] += 1
            for arm in ("T","H"):
                c = cells[arm]
                reasons = tuple(k for k, flag in (("applicable", c["primary"] < r["denom"]), ("misuse", c["MR"] < 0), ("incomplete", c["completeness"] < required_completeness)) if flag)
                contrasts[arm + "/" + "+".join(reasons)] += 1
            counts["gate_only_nonbold_above_both"] += all(cells["G"]["nonbold"]>cells[a]["nonbold"] for a in ("T","H"))
    report[required_completeness] = dict(counts=counts, profiles=len(profiles), winning_profiles=len(winning_groups), endpoint_errors_on_gate_only=contrasts)
print(json.dumps(report,indent=2))
