"""Verify settled capability results against their receipts and locate realized changes."""
from argparse import ArgumentParser
from collections import Counter
import json
from unittest.mock import patch

from qamc.common import sha

import decision_capability as method
import run_decision_capability as run


def audit(part):
    out = run.BASE_OUT / part
    state, spec, settlement = (run.read(out / file)
                               for file in ("RUN_STATE.json", "FROZEN.json", "SETTLED.json"))
    if state["state"] != "COMPLETE":
        raise ValueError("Expected a completed run")
    verified = []

    def verify(path, rebuilt):
        if run.read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Receipt replay differs for {path.name}")
        verified.append(path.name)

    with patch.object(run.probe, "freeze", verify):
        run.main("report", part)

    ledger = settlement["ledger"]
    keys = {(rec["unit"]["stage"], rec["request_sha256"]) for rec in ledger}
    if len(keys) != len(ledger) or len(keys) != state["physical_requests"]:
        raise ValueError("Physical ledger has duplicate or missing requests")
    stage_counts = Counter(rec["unit"]["stage"] for rec in ledger)
    if any(count > spec["cap"].get(stage, 0) for stage, count in stage_counts.items()):
        raise ValueError("Launch count exceeds frozen allocation")

    _, _, roots, _, _, _ = run.prepare(part)
    divergence, paired_fields = [], Counter()
    correction = Counter()
    original_allowed = method.allowed

    def allow_constraint_compliant_option(action, block):
        reason = original_allowed(action, block)
        if reason == "INVALID_OPTIONAL_STRENGTH" and action["operation"] == "ADD_OPTION":
            return original_allowed({**action, "extent": "SUPPORT"}, block)
        return reason

    for row in settlement["rows"]:
        execution = row["execution"]
        a = execution["answers"].get(method.GENERIC)
        b = execution["answers"].get(method.BOUND)
        fields_a, fields_b = (row["native"][arm]["fields"] for arm in (method.GENERIC, method.BOUND))
        paired_fields.update(fields_a.keys() & fields_b.keys())
        if a is None or b is None:
            continue
        if a["answer"] == b["answer"]:
            if a["judge_sha256"] != b["judge_sha256"] or fields_a != fields_b:
                raise ValueError("Identical answers received different native scoring")
            continue
        raw = method.read_object(execution["bind_raw"])["edits"]
        rejections = [dict(item, operation=raw[item["index"]]) for item in b["rejected"]
                      if item not in a["rejected"]]
        if not rejections:
            raise ValueError("Answer divergence has no treatment-specific rejection")
        with patch.object(method, "allowed", allow_constraint_compliant_option):
            corrected = method.compile_edits(
                roots[row["uid"]], execution["blocks"], execution["bind_raw"], method.BOUND)
        if corrected["answer"] == a["answer"]:
            correction["same_as_generic"] += 1
        elif corrected["answer"] == b["answer"]:
            correction["same_as_bound"] += 1
        else:
            correction["new_unscored_answer"] += 1
        divergence.append({
            "uid": row["uid"], "group": row["group"], "labels": row["labels"],
            "generic_fields": fields_a, "bound_fields": fields_b,
            "bound_only_rejections": rejections,
            "changed_slots": {arm: execution["answers"][arm]["changed_slots"]
                              for arm in (method.GENERIC, method.BOUND)},
        })
    return {
        "assigned": len(settlement["rows"]),
        "physical_requests": len(keys),
        "report_replay": verified,
        "paired_fields": paired_fields,
        "rejections_by_reason": Counter(item["reason"] for row in divergence
                                        for item in row["bound_only_rejections"]),
        "answers_differ": len(divergence),
        "source_groups_with_differences": len({row["group"] for row in divergence}),
        "hard_constraint_add_option_diagnostic_divergent_cases": correction,
        "per_case_differences": divergence,
        "new_model_requests": 0,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=("smoke", "pilot"))
    args = parser.parse_args()
    print(json.dumps(audit(args.part), ensure_ascii=False, indent=2))
