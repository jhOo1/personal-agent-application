"""Check task-only participant roles on the archived set of distinct decision plans."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import run_outcome_contract as parent
import run_task_conditioned_value as runtime
from settle_joint_planning import usage
import task_decision_roles as model


STAGE, ARM = "TaskDecisionRoles", "TASK_ONLY"
OUT = parent.OUT.with_name("task_decision_role_diagnostic_v1")
RUN = parent.RUN.with_name(OUT.name)
probe, read, replay = parent.probe, parent.read, parent.replay


def prepare(reference):
    source = parent.OUT / (parent.CONTRACT + "_MANIFEST.json")
    tasks = model.partition_tasks(read(source))
    if len(tasks) != 12:
        raise ValueError("The archived 12-task decision plans have changed")
    jobs = [(uid, ARM, model.role_request(**item)) for uid, item in tasks.items()]
    code = (Path(__file__), Path(model.__file__), Path(runtime.__file__))
    spec = {"panel": "archived_tasks", "caps": {STAGE: len(jobs)}, "service_reference_sha256": reference,
            "source_sha256": sha(source.read_bytes()), "wire_shas": {uid: sha(wire) for uid, _, wire in jobs},
            "implementation_sha256": {p.name: sha(p.read_bytes()) for p in code},
            "independent_confirmation": False}
    return spec, jobs, tasks, {}, None, {STAGE: {}}


def evaluate(inputs, stage):
    _, jobs, tasks, *_ = inputs
    responses = stage(STAGE, jobs)
    results = {}
    for uid, arm, wire in jobs:
        record, answer = responses[uid, arm]
        result = {"request_sha256": sha(wire), "status": record["status"], "roles": []}
        if record["status"] == "OK":
            try:
                result["roles"] = model.parse_roles(**tasks[uid], raw=answer)
            except ValueError as error:
                result.update(status="INVALID_ROLE_CONTRACT", diagnosis=str(error))
        results[uid] = result
    return results, [{"task_sha256": uid, **item} for uid, item in tasks.items()]


def summarize(spec, contracts, rows, ledger):
    pairs, states = Counter(), Counter()
    mixed, separated, valid_decisions, clarifications = 0, 0, 0, 0
    for result in contracts.values():
        states[result["status"]] += 1
        decisions = [role for role in result["roles"] if role["kind"] == "DECISION"]
        clarifications += len(result["roles"]) - len(decisions)
        valid_decisions += len(decisions)
        parties = {(role["executor"], role["beneficiary"]) for role in decisions}
        mixed += len({beneficiary for _, beneficiary in parties} - {"UNKNOWN"}) > 1
        separated += ("SELF", "OTHER") in parties
        pairs.update(role["executor"] + "/" + role["beneficiary"] for role in decisions)
    return {"assigned_tasks": len(rows), "validated_decisions": valid_decisions,
            "validated_clarifications": clarifications, "status": states, "role_pairs": pairs,
            "tasks_with_multiple_resolved_beneficiary_classes": mixed,
            "tasks_with_self_execution_and_other_beneficiary": separated,
            "usage": usage(ledger), "scope_validated_by_model_and_literal_anchors_only": True}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    action = parser.parse_args().action
    freeze = OUT / "FROZEN.json"
    reference = probe.read_reference()[1] if action == "freeze" else read(freeze)["service_reference_sha256"]
    inputs = prepare(reference)
    with (
        probe.runner_lock(RUN / "runner.lock"),
        patch.object(runtime, "OUT", OUT),
        patch.object(runtime, "evaluate", evaluate),
        patch.object(runtime, "summarize", summarize),
    ):
        if action == "freeze":
            runtime.manifest(inputs[0]["panel"], STAGE, inputs[1])
            probe.freeze(freeze, inputs[0])
            return
        probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT
        terminal = OUT / "RUN_STATE.json"
        done = terminal.exists() and read(terminal)["state"] == "COMPLETE"
        if action == "run" and not done:
            runtime.execute(inputs, live=True)
        elif action == "verify":
            if not done:
                raise ValueError("Await terminal role records")

            def exact(path, value):
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError(f"Role replay differs at {path.name}")

            with patch.object(probe, "freeze", exact):
                runtime.execute(inputs, live=False)
            print(json.dumps({"new_model_calls": 0, "verified": True}))


if __name__ == "__main__":
    main()
