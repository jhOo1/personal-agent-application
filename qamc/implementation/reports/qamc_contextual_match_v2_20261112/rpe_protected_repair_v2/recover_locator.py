"""Measure a separate recovery arm for valid locator content with extra fields."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from audit_protected_repair import project_locator
from protected import FORMATS, REVISE, apply, default_answer
from qamc.common import sha
from qamc.contextual_match.development import text_request
import repair_trial as trial


HERE = Path(__file__).resolve().parent
PARENT = trial.RUN
RUN = PARENT.with_name("rpe_protected_repair_v2_locator_recovery")


def inventory():
    packets, binding, veto, _, old_pin = trial.assign()
    if trial.read(PARENT / "FROZEN.json") != old_pin:
        raise ValueError("Parent experiment drift")
    records = trial.read(PARENT / "DIAGNOSES.json")
    if records.keys() != packets.keys():
        raise ValueError("Parent locator inventory is incomplete")
    project = {}
    for key, row in records.items():
        if row["state"] == "INVALID_LOCATOR" and row["error"] == "invalid target operation":
            plan = project_locator(row["receipt"]["answer"], packets[key])
            if plan is not None:
                project[key] = plan
    wires = {}
    for key, plan in project.items():
        payload = {**packets[key], "proposed_diagnosis": plan}
        for arm in trial.ARMS:
            wires[key, arm] = text_request(REVISE + "\n\n" + FORMATS[arm], payload, trial.MODEL, 8192)
    wires = dict(sorted(wires.items(), key=lambda row: sha(["locator-field-projection", *row[0]])))
    caps = {trial.REPAIR_STAGE: len(wires), trial.SCORE_STAGE: len(wires)}
    pin = {"parent_freeze": sha(old_pin), "parent_locator": sha(records),
           "projected_count": len(project), "canonical_diagnoses": sha(project),
           "repair_wire_sha256": sha(list(wires.values())), "caps": caps,
           "code_sha256": {name: sha((HERE / name).read_bytes())
                           for name in ("audit_protected_repair.py", "recover_locator.py", "readouts.sh", "LOCATOR_RECOVERY.md")}}
    return packets, binding, veto, project, wires, caps, pin


def run_projection(packets, binding, project, wires, identity, ledger):
    replies = trial.stage(trial.REPAIR_STAGE, wires, identity, ledger)
    delivered = {}
    for key, plan in project.items():
        packet = packets[key]
        original = default_answer(packet)
        delivered[key] = {}
        for arm in trial.ARMS:
            result = replies[key, arm]
            state, final, error = result["status"], None, None
            if state == "OK":
                try:
                    final = apply(result["answer"], packet, plan, arm)
                    state = "KEEP" if final == original else "EDITED"
                except (TypeError, ValueError, KeyError) as exc:
                    state, final, error = "INVALID_REVISION", original, str(exc)
            delivered[key][arm] = {"status": state, "answer": final, "error": error, "receipt": result}
    trial.probe.freeze(RUN / "LOCKED_EXTENSION_ANSWERS.json", delivered)
    return trial.measure({key: packets[key] for key in project}, binding, delivered, identity, ledger)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    packets, binding, veto, project, wires, caps, pin = inventory()
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.engine.CAP = caps
    RUN.mkdir(parents=True, exist_ok=True)
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            trial.probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if pin != trial.read(RUN / "FROZEN.json"):
            raise ValueError("Recovery inputs differ from the freeze")
        parent_grades = trial.read(PARENT / "GRADED_ANSWERS.json")
        parent_cost = trial.read(PARENT / "LEDGER.json")
        if action == "run" and not (RUN / "LEDGER.json").is_file():
            identity = {"experiment_sha256": sha(pin),
                        "service_reference_sha256": trial.probe.read_reference()[1]}
            if identity["service_reference_sha256"] != trial.read(PARENT / "EXECUTION.json")["service_reference_sha256"]:
                raise ValueError("Continuation service identity differs")
            trial.probe.freeze(RUN / "EXECUTION.json", identity)
            ledger = []
            recovered = run_projection(packets, binding, project, wires, identity, ledger)
            if len(ledger) > sum(caps.values()):
                raise ValueError("Continuation request cap exceeded")
            trial.probe.freeze(RUN / "LEDGER.json", ledger)
        else:
            recovered = trial.read(RUN / "GRADED_ANSWERS.json")
            ledger = trial.read(RUN / "LEDGER.json")
        if recovered.keys() != project.keys():
            raise ValueError("Recovery grade inventory differs")
        composite = {**parent_grades, **recovered}
        result = trial.summarize(packets, binding, veto, composite, parent_cost + ledger)
        tokens = [(row.get("usage") or {}).get("total_tokens") for row in ledger]
        extra = {"projected": len(project), "physical_requests": len(ledger),
                 "tokens": sum(t or 0 for t in tokens), "unknown_usage": tokens.count(None),
                 "repair_dispositions": {arm: Counter(row[arm]["status"] for row in recovered.values())
                                         for arm in trial.ARMS}}
        trial.probe.freeze(RUN / "INCREMENTAL_COST.json", extra)
        print(json.dumps({"projection": extra, "composite": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
