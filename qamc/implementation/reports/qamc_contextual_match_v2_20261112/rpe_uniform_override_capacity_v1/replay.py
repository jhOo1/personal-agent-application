"""Outcome-informed capacity of uniform overrides of an existing routed answer."""
from collections import defaultdict
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
rows = json.loads((root / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]
incumbent = "IPE_C"
arms = (incumbent, "TASK_ONLY", "RPR_PAPER_FULL")


def vector(cell):
    grade = cell["grade"]
    match = grade["match"]
    return (match["matched"], int(match["matched"] == match["positions"]),
            *(-grade[k] for k in ("OPB", "UPB", "FM", "RII", "VG")))


def analyze(group_key, clean, panel_rows):
    groups = defaultdict(list)
    for row in panel_rows:
        groups[row[group_key]].append(row)
    gains = [0, 0]
    available = exact = positions = closed = useful = changed = 0
    for block in groups.values():
        eligible = [r for r in block if all(c["grade"].get("match") and
                    (not clean or not c["flags"]) for c in r["scores"].values())]
        available += len(eligible)
        original = [vector(r["scores"][incumbent]) for r in eligible]
        positions += sum(v[0] for v in original)
        exact += sum(v[1] for v in original)
        if len(eligible) != len(block):
            continue
        closed += 1
        choices = []
        for arm in arms:
            proposed = [vector(r["scores"][arm]) for r in block]
            if all(all(x >= y for x, y in zip(p, o)) for p, o in zip(proposed, original)):
                delta = tuple(sum(p[i]-o[i] for p,o in zip(proposed,original)) for i in (1,0))
                edits = sum(r["scores"][arm]["answer_sha256"] != r["scores"][incumbent]["answer_sha256"] for r in block)
                choices.append((*delta, -edits))
        de, dp, neg_edits = max(choices)
        gains[0] += de
        gains[1] += dp
        useful += int(de > 0 or dp > 0)
        changed -= neg_edits
    return dict(tasks=available, incumbent_exact=exact, incumbent_positions=positions,
                assigned_groups=len(groups), complete_groups=closed, improving_groups=useful,
                changed_answers=changed, gain_exact=gains[0], gain_positions=gains[1])


assert len(rows) == len({r["uid"] for r in rows}) == 300
frozen = json.loads((root / "counterfactual_rpeval_v41/FROZEN.json").read_text())
assert not frozen["independent_confirmation"]
task_map = {r["uid"]: r for r in frozen["roots"]}
rows = [r for r in rows if r["uid"] in task_map]
assert len(rows) == len(task_map) == 233
for r in rows:
    meta = task_map[r["uid"]]
    assert r["source_group"] == meta["group"]
    if r["task_wire_sha256"]:
        assert r["task_wire_sha256"] == meta["task_wire_sha256"]
    r["task_wire_sha256"] = meta["task_wire_sha256"]
assert all(r["task_wire_sha256"] for r in rows if all(c["grade"].get("match") for c in r["scores"].values()))
output = {}
for panel, clean in (("all", False), ("no_flags", True)):
    incomplete = {r["task_wire_sha256"] for r in rows if any(
        not c["grade"].get("match") or (clean and c["flags"]) for c in r["scores"].values())}
    complete_rows = [r for r in rows if r["task_wire_sha256"] not in incomplete]
    output[panel] = {key: analyze(key, clean, rows) for key in ("uid", "task_wire_sha256")}
    output[panel]["individual_on_same_complete_blocks"] = analyze("uid", clean, complete_rows)
print(json.dumps(output, indent=2))
