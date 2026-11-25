"""Reconstruct per-answer generation cost without sending any model requests."""
from argparse import ArgumentParser
from collections import Counter
import json

from deployment_cost import numeric_cost, old_cost, profile
from qamc.common import sha

import audit_main_answer_revision as audit
import run_main_answer_revision as run


def base_receipts(archive, ledger):
    previous = run.replay.old_receipts(archive)[run.parent.parent.ACTOR]
    result = {(run.parent.parent.ACTOR, digest): record for digest, (record, _) in previous.items()}
    directories = (run.joint.parent.OUT, run.joint.OUT, run.joint.OUT.with_name("rp_seed_minimal_revision_rpeval_v1"),
                   run.joint.OUT.with_name("focal_memory_rpeval_v1"))
    for directory in directories:
        path = directory / "Actor_EXACT.json"
        if not path.exists():
            continue
        for digest, (record, _) in run.read(path).items():
            if digest != record["request_sha256"]:
                raise ValueError("Inherited Actor receipt belongs to a different request")
            result.setdefault(("Actor", digest), record)
    for rec in ledger:
        result[rec["unit"]["stage"], rec["request_sha256"]] = rec
    return result


def available(rec):
    return numeric_cost(rec["usage"]) if rec and rec["status"] == "OK" else None


def readout(phase):
    spec, jobs, _, old, archive = run.prepare()
    if spec != run.read(run.OUT / "FROZEN.json"):
        raise ValueError("Revision inputs changed")
    _, parents, ledger = run.checked()
    receipts = base_receipts(archive, ledger)
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    editor, _, _, _ = audit.editor_audit(spec, jobs, old, archive)
    by_hash = {rec["request_sha256"]: rec for rec, _ in editor.values()}
    official = run.read(run.joint.prior.formal.OUT / "PLAN.json")
    roots = {row["uid"]: row for row in archive["roots"]}
    controls = (run.MAIN, run.GATE, run.RP)
    arms = (*run.edit.ARMS, *controls)
    status = Counter()
    costs = []
    for row in parents:
        uid = row["uid"]
        selected = available(receipts.get(("Selector", row["selection"]["request_sha256"])))
        actor = row["actor"][run.edit.realization.SEGMENTED]
        drafted = available(receipts.get(("Actor", actor.get("request_sha256")))) if actor["status"] == "OK" else None
        if selected is None or drafted is None:
            status["missing_parent_cost"] += 1
            continue
        original = selected + drafted
        root = roots[uid]
        usage = {run.MAIN: original}
        calls = {run.MAIN: 2}
        for method in (run.GATE, run.RP):
            archived_cost = old_cost(official, root, method)
            if archived_cost is not None:
                usage[method] = archived_cost
                calls[method] = len(run.joint.prior.formal.STAGES[method])
        for arm in run.edit.ARMS:
            if spec["non_dispatch"].get(uid) == "NO_MAIN_LICENSE":
                usage[arm], calls[arm] = original, 2
            else:
                reply = by_hash.get(spec["wire_sha256"].get(f"{uid}/{arm}"))
                edited = available(reply)
                if edited is not None:
                    usage[arm], calls[arm] = original + edited, 3
                else:
                    status[f"{arm}/missing_editor_cost"] += 1
        costs.append({"uid": uid, "group": row["group"], "usage": usage, "calls": calls})

    panels = {"reported_generation_usage_only": costs}
    if phase == "terminal":
        if run.read(run.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Expected terminal grading")
        saved = {row["uid"]: row for row in run.read(run.OUT / "SETTLED.json")["rows"]}
        panels["with_all_native_match"] = [r for r in costs if all(
            saved[r["uid"]]["native"][arm]["fields"].get("match") is not None for arm in arms)]
    combined = {}
    for name, panel in panels.items():
        common = [row for row in panel if all(arm in row["usage"] for arm in arms)]
        combined[name] = {
            **profile(common, arms),
            "logical_generation_calls_before_cache": {arm: sum(row["calls"][arm] for row in common) for arm in arms},
        }
    return {"cost_panels": combined, "unavailable": status, "new_requests": 0,
            "interpretation": "Measured successful inference path before exact reuse. "
                              "Includes shared selector, draft and editor where used. "
                              "Native judge charges and unknown usage are excluded."}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preliminary", "terminal"))
    print(json.dumps(readout(parser.parse_args().phase), indent=2, sort_keys=True))
