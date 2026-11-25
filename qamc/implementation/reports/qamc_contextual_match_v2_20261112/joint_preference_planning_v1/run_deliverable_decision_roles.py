"""Compare a direct task-only decision plan with the archived role annotation."""
from argparse import ArgumentParser
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import parse_object, sha

from audit_task_role_partition import separate_slots
from decision_witness_v45 import task_text
from planning import request, text
import run_task_decision_roles as previous
from thinking_budget_transport import controlled_wire


OUT = previous.OUT.with_name("deliverable_decision_role_diagnostic_v1")
RUN = previous.RUN.with_name(OUT.name)
STAGE = "DeliverableDecisionRoles"
probe, read, runtime = previous.probe, previous.read, previous.runtime

PROMPT = """Read only the current task. Identify the concrete choices an answer must
make or recommend to deliver what was asked. Return a short list of those choices,
with a public task quotation and with who will carry out and experience each choice.

A decision describes what the answer will choose, change, recommend or present.
A missing detail such as a location, budget or age can affect a decision, but
asking for that detail is not the decision. Keep a real decision even if a fact
needed to give a definitive recommendation is unknown. Assign UNKNOWN where needed.
Include only choices within the requested deliverable. Use distinct rows for
logistics the requester controls for themselves and an outcome someone else
experiences only if they are genuinely separate choices in this task. A single
shared outcome can be a single row. Do not invent a private choice to force a split.

For both roles use SELF for the requester, OTHER for an identified person or group
excluding the requester, SHARED for the requester and others together, and UNKNOWN
if the current task does not establish the relationship. The requester can execute
an arrangement whose experience belongs to someone else. The choice text names
what is decided; it must not provide the selected answer.

Return exactly {"decisions":[{"choice":"<choice to make>","executor":"SELF",
"beneficiary":"OTHER","task_quote":"<exact continuous quotation from the current task>"}]}.
Use one to six rows. Return {"decisions":[]} only if the task requests no action,
recommendation or deliverable choice. No prose outside JSON."""


def parse_decisions(task, raw):
    data = parse_object(raw)
    if set(data) != {"decisions"} or not isinstance(data["decisions"], list) or len(data["decisions"]) > 6:
        raise ValueError("Expected at most six decision rows")
    anchors = tuple(task_text(task))
    seen = set()
    roles = []
    for slot, row in enumerate(data["decisions"], 1):
        if not isinstance(row, dict) or set(row) != {"choice", "executor", "beneficiary", "task_quote"}:
            raise ValueError("Unrecognized decision row")
        choice = row["choice"]
        if not text(choice, 300) or choice.strip().casefold() in seen:
            raise ValueError("Expected a distinct decision description")
        seen.add(choice.strip().casefold())
        if any(not isinstance(row[key], str) or row[key] not in previous.model.PARTIES
               for key in ("executor", "beneficiary")):
            raise ValueError("Unrecognized participant relationship")
        quote = row["task_quote"]
        if not text(quote, 300) or not any(quote in anchor for anchor in anchors):
            raise ValueError("Decision quote must come from the current public task")
        roles.append({"slot": slot, "kind": "DECISION", **row})
    return roles


def prepare(reference):
    frozen_previous = read(previous.OUT / "FROZEN.json")
    settled_path = previous.OUT / "SETTLED.json"
    settled = read(settled_path)
    tasks = {row["task_sha256"]: row["task"] for row in settled["rows"]}
    if {sha(task) for task in tasks.values()} != tasks.keys() or tasks.keys() != frozen_previous["wire_shas"].keys():
        raise ValueError("The completed task-only panel changed")
    jobs = [(uid, previous.ARM, controlled_wire(request({"task": task}, PROMPT, 8192), previous.model.BUDGET))
            for uid, task in tasks.items()]
    spec = {"panel": "same_archived_tasks_direct_roles", "caps": {STAGE: len(jobs)},
            "service_reference_sha256": reference, "old_settlement_sha256": sha(settled_path.read_bytes()),
            "wire_shas": {uid: sha(wire) for uid, _, wire in jobs}, "independent_confirmation": False,
            "implementation_sha256": {p.name: sha(p.read_bytes()) for p in
                                      (Path(__file__), Path(runtime.__file__),
                                       Path(separate_slots.__code__.co_filename))}}
    return spec, jobs, tasks, settled["contracts"], None, {STAGE: {}}


def evaluate(inputs, stage):
    _, jobs, tasks, archived, *_ = inputs
    responses = stage(STAGE, jobs)
    results = {}
    for uid, arm, wire in jobs:
        record, raw = responses[uid, arm]
        result = {"request_sha256": sha(wire), "status": record["status"], "roles": []}
        if record["status"] == "OK":
            try:
                result["roles"] = parse_decisions(tasks[uid], raw)
            except ValueError as error:
                result.update(status="INVALID_DECISION_CONTRACT", diagnosis=str(error))
        result["old_role_status"] = archived[uid]["status"]
        result["old_roles"] = archived[uid]["roles"]
        results[uid] = result
    return results, [{"task_sha256": uid, "task": task} for uid, task in tasks.items()]


def summarize(spec, contracts, rows, ledger):
    output = previous.summarize(spec, contracts, rows, ledger)
    locations = [separate_slots(row["roles"]) for row in contracts.values() if row["status"] == "OK"]
    output["separate_self_and_external_beneficiary_tasks"] = sum(
        bool(value["requester_benefits"] and value["external_benefits"]) for value in locations
    )
    output["old_common_valid_tasks"] = sum(row["status"] == row["old_role_status"] == "OK" for row in contracts.values())
    return output


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
            probe.freeze(freeze, inputs[0])
            return
        probe.OUT, probe.RUN, previous.replay.OUT = OUT, RUN, OUT
        terminal = OUT / "RUN_STATE.json"
        done = terminal.exists() and read(terminal)["state"] == "COMPLETE"
        if action == "run" and not done:
            runtime.execute(inputs, live=True)
        elif action == "verify":
            if not done:
                raise ValueError("Await terminal deliverable-role records")

            def exact(path, value):
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError(f"Deliverable-role replay differs at {path.name}")

            with patch.object(probe, "freeze", exact):
                runtime.execute(inputs, live=False)
            print(json.dumps({"new_model_calls": 0, "verified": True}))


if __name__ == "__main__":
    main()
