"""Replay two fixed, prediction-only routes over archived RPEval responses."""
from collections import Counter
import json

import run_main_answer_revision as run
from settle_joint_planning import score_matrix, subsets


TASK = "TASK_ONLY"
RP_ROUTE = "TASK_ONLY_IF_RP_HAS_NO_C"
GUARD_ROUTE = "USE_MAIN_IF_GUARD"
MAIN_ROUTE = "USE_MAIN_IF_MAIN_LICENSE"
ROUTES = {GUARD_ROUTE: {"GUARD"}, MAIN_ROUTE: {"GUARD", "STYLE_OR_CONTENT"}}


def audit():
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("Expected settled current revisions")
    parent = {r["uid"]: r["selection"] for r in run.read(run.parent.parent.OUT / "SETTLED.json")["rows"]}
    frozen = run.read(run.OUT / "FROZEN.json")
    rows, dispositions = [], Counter()
    for record in run.read(run.OUT / "SETTLED.json")["rows"]:
        sel = parent[record["uid"]]
        native = dict(record["native"])
        routes = {}
        for arm, allowed in ROUTES.items():
            if sel["status"] != "OK":
                native[arm], routes[arm] = {"fields": {}, "status": "SELECTOR_UNAVAILABLE"}, "UNAVAILABLE"
            else:
                anchor = run.MAIN if any(edge["use"] in allowed for edge in sel["uses"]) else TASK
                native[arm], routes[arm] = native[anchor], anchor
            dispositions[f"{arm}/{routes[arm]}"] += 1
        rows.append({**record, "native": native, "routes": routes})
    methods = (GUARD_ROUTE, MAIN_ROUTE, TASK, run.MAIN, run.edit.BOUND, run.GATE, run.RP, RP_ROUTE)
    results = {}
    panels = subsets(rows, frozen)
    panels["less_exposed"] = [row for row in rows if row["less_exposed"]]
    for name, panel in panels.items():
        matrix = score_matrix(panel, methods)
        comparisons = {control: {
            "match": run.replay.paired(panel, control, GUARD_ROUTE),
            **{f: run.joint.parent.comparisons.grade_pair(panel, control, GUARD_ROUTE, f)
               for f in ("OPB", "UPB", "FM", "VG")},
        } for control in (MAIN_ROUTE, TASK, run.MAIN, run.edit.BOUND, run.GATE, run.RP, RP_ROUTE)}
        counts = Counter(row["routes"][GUARD_ROUTE] for row in panel)
        results[name] = {"joint": matrix, "paired": comparisons, "guard_routing": counts}
    return {"assigned": len(rows), "route_assignments": dispositions, "panels": results,
            "new_requests": 0, "independent_confirmation": False,
            "interpretation": "Retrospective replay uses only frozen predictions to select a previously scored answer. "
                              "Reference labels are joined after routing and no result has been rescored."}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
