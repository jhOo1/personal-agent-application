"""Consolidate exact V42 evidence from one stable settled-wave prefix."""
from argparse import ArgumentParser
import json
from pathlib import Path

from qamc.common import sha

from assess_visibility_v42 import numeric_screen
from audit_visibility_v42 import analyze as audit_wires
from compare_task_only_v42 import analyze as compare_task_only
from cost_visibility_v42 import summarize as measure_cost
from diagnose_visibility_v42 import settled_judges
import run_visibility_v42 as study


def stable_prefix(plan):
    records = []
    for index, uids in enumerate(plan["waves"]):
        path = study.OUT / f"wave_{index:02d}" / "COMPLETED.json"
        if not path.exists():
            break
        records.append({"wave": index, "roots": len(uids), "sha256": sha(path.read_bytes())})
    return records


def settle(expected=None):
    frozen = study.read(study.OUT / "FROZEN.json")
    if frozen != study.prepare():
        raise ValueError("Pinned execution files changed")
    old = stable_prefix(frozen)
    roots = sum(wave["roots"] for wave in old)
    planned = sum(map(len, frozen["waves"]))
    status = study.read(study.OUT / "RUN_STATE.json")
    if expected is None and (status["state"] != "COMPLETE" or roots != planned):
        raise ValueError("Terminal settlement requires a COMPLETE worker state and the full cohort")
    if expected is not None and expected != roots:
        raise ValueError(f"Expected a {expected}-root prefix, found {roots}")
    scored, wires, judge, task_only, cost = (
        study.report(frozen), audit_wires(), settled_judges(), compare_task_only(), measure_cost()
    )
    if (stable_prefix(frozen) != old or roots != scored["completed"]
            or roots != wires["checked"].get("roots", 0) or roots != judge["settled"]
            or roots != task_only["completed_roots"] or roots != cost["settled"]):
        raise ValueError("Wave settled during reconciliation; read a new stable prefix")
    if scored["physical_receipts"] != cost["new_physical_receipts"] or scored["physical_receipts"] != sum(
        wires["checked"].get(stage + "/new", 0) for stage in study.CAP
    ):
        raise ValueError("Physical request totals disagree")
    terminal = status["state"] == "COMPLETE" and roots == scored["planned"]
    return {"phase": status, "wave_proofs": old, "completed_roots": roots, "scores": scored,
            "wire_audit": wires, "score_sensitivity": judge, "task_only_comparison": task_only,
            "independent_online_cost": cost, "decision": numeric_screen(scored, terminal),
            "new_model_calls": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=int, help="Permit the specified interim settled prefix.")
    parser.add_argument("--output", type=Path, help="Write a validated report to a new file.")
    args = parser.parse_args()
    result = settle(args.expected)
    if args.output:
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
