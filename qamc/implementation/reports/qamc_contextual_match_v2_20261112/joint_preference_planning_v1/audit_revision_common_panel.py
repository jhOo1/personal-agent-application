"""Read-only RPEval score coverage and matched deployment-arm comparisons."""
from argparse import ArgumentParser
from collections import Counter
import json

from qamc.common import sha

import audit_main_answer_revision as audit
import run_main_answer_revision as run
from settle_joint_planning import score_matrix, subsets


METHODS = (*run.edit.ARMS, run.MAIN, run.GATE, run.RP)


def checks_and_replay():
    inputs = run.prepare()
    spec, jobs, _, old, archive = inputs
    if spec != run.read(run.OUT / "FROZEN.json"):
        raise ValueError("The score panel does not match the frozen design")
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    editor, compiled, revised, editors = audit.editor_audit(spec, jobs, old, archive)
    if (len(editor) != editors["editor_request_hashes_checked"]
            or any(rec["status"] == "PENDING_DELIVERY_UNKNOWN" for rec, _ in editor.values())):
        raise ValueError("Wait for editor receipts to settle before replaying scores")
    _, expected, prior, _ = audit.grading_allocation(compiled, revised, spec, archive)
    scores = audit.verify_receipts(run.JUDGE, expected)
    editor_by_hash = {rec["request_sha256"]: (rec, raw) for rec, raw in editor.values()}
    judge_by_hash = {**prior, **{rec["request_sha256"]: (rec, raw) for rec, raw in scores.values()}}

    def stage(name, calls):
        source = editor_by_hash if name == run.EDITOR else judge_by_hash
        result = {}
        for uid, arm, wire in calls:
            digest = sha(wire)
            if name == run.JUDGE and digest not in expected and digest not in prior:
                raise ValueError("Scoring replay produced an unallocated request")
            result[uid, arm] = source.get(digest, ({"status": "NOT_DISPATCHED", "request_sha256": digest}, None))
        return result

    return spec, run.evaluate(inputs, stage), scores, expected


def availability(rows, scores, expected):
    status = Counter(rec["status"] for rec, _ in scores.values())
    status["NOT_DISPATCHED"] = len(expected) - len(scores)
    return {
        "physical_judge_status": status,
        "native_match_rows": {method: sum(row["native"][method]["fields"].get("match") is not None for row in rows)
                              for method in METHODS},
        "logical_rows": len(rows),
    }


def matched_strata(spec, rows):
    panels = subsets(rows, spec)
    panels["less_exposed"] = [row for row in rows if row["less_exposed"]]
    changed = {name: [] for name in ("neither_changed", "both_changed", "only_generic", "only_decision")}
    for row in rows:
        generic, decision = (row["revisions"][arm]["status"] == "APPLIED" for arm in run.edit.ARMS)
        panel = ("both_changed" if generic and decision else "only_generic" if generic
                 else "only_decision" if decision else "neither_changed")
        changed[panel].append(row)
    panels.update(changed)
    outcomes = {}
    for name, panel in panels.items():
        result = score_matrix(panel, METHODS)
        common = [row for row in panel if all(row["native"][m]["fields"].get("match") for m in METHODS)]
        if len(common) != result["common_match_cases"]:
            raise ValueError("Joint scoring eligibility changed")
        matches = {}
        for control in METHODS:
            if control == run.edit.BOUND:
                continue
            pair = run.replay.paired(common, control, run.edit.BOUND)
            matches[control] = {key: pair[key] for key in
                                ("valid_cases", "match_delta", "95pct_source_bootstrap") if key in pair}
        outcomes[name] = {**result, "decision_vs_control_on_same_rows": matches}
    return outcomes


def audit_panel(phase):
    spec, rows, scores, expected = checks_and_replay()
    state = run.read(run.OUT / "RUN_STATE.json")
    observed = availability(rows, scores, expected)
    if phase != "terminal":
        return observed
    if state["state"] != "COMPLETE":
        raise ValueError("Final score matrix requires terminal receipts")
    saved = run.read(run.OUT / "SETTLED.json")["rows"]
    if rows != saved:
        raise ValueError("Read-only replay does not reproduce the settled native rows")
    return {**observed, "five_method_intersections": matched_strata(spec, rows),
            "new_requests": 0, "independent_confirmation": False}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("availability", "terminal"))
    print(json.dumps(audit_panel(parser.parse_args().phase), indent=2, sort_keys=True))
