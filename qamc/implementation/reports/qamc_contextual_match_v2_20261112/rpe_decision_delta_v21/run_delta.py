"""Compare single-call decision edits with a matched free editor."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from delta import COMMON, DELTA, FREE, apply, index
from qamc.common import sha
from qamc.contextual_match.development import text_request
import repair_trial as trial


HERE = Path(__file__).resolve().parent
RUN = trial.RUN.with_name(HERE.name)
ARMS = ("FREE", "DELTA")
STAGE = "DecisionEdit"
CAPS = {STAGE: 48, trial.SCORE_STAGE: 48}


def assign():
    originals, binding, choices, _, parent = trial.assign()
    if trial.read(trial.RUN / "FROZEN.json") != parent:
        raise ValueError("Parent comparison freeze failed")
    packets, jobs = {}, {}
    prompts = {"FREE": FREE, "DELTA": DELTA}
    for key, old in originals.items():
        chosen = choices[key]["choice"] or old["default_id"]
        original = old["candidates"][chosen]
        packet = {**old, "default_id": chosen, "draft_units": index(original)}
        packets[key] = packet
        visible = {"context": packet["context"], "draft_units": packet["draft_units"],
                   "alternative_solutions": {cid: answer for cid, answer in old["candidates"].items()
                                             if cid != chosen}}
        for arm in ARMS:
            jobs[key, arm] = text_request(COMMON + "\n\n" + prompts[arm], visible, trial.MODEL, 8192)
    jobs = dict(sorted(jobs.items(), key=lambda row: sha(["rpe-decision-delta-v21", *row[0]])))
    pin = {"assigned": len(packets), "base_parent": sha(parent), "v1_choices": sha(choices),
           "binding_sha256": sha(binding), "inference_sha256": sha(list(jobs.values())),
           "caps": CAPS, "code_sha256": {name: sha((HERE / name).read_bytes()) for name in
                                       ("delta.py", "run_delta.py", "run.sh", "PROTOCOL.md")}}
    return packets, binding, choices, jobs, pin


def generate(packets, jobs, identity, ledger):
    received = trial.stage(STAGE, jobs, identity, ledger)
    rows = {}
    for key, packet in packets.items():
        base = packet["candidates"][packet["default_id"]]
        rows[key] = {}
        for arm in ARMS:
            receipt = received[key, arm]
            state, final, info, error = receipt["status"], None, None, None
            if state == "OK":
                try:
                    final, info = apply(receipt["answer"], packet, arm)
                    state = "KEEP" if final == base else "EDITED"
                    if info["rejected_groups"]:
                        state = "PARTIAL_EDIT" if final != base else "GROUP_FALLBACK"
                except (TypeError, ValueError, KeyError) as exc:
                    final, state, error = base, "INVALID_EDIT", str(exc)
            rows[key][arm] = {"status": state, "answer": final, "diagnostics": info,
                              "error": error, "receipt": receipt}
    trial.probe.freeze(RUN / "LOCKED_ANSWERS.json", rows)
    return rows


def delta_bounds(rows, arm, ref):
    low = high = 0
    for row in rows:
        left, right = (row["grade"][method] for method in (arm, ref))
        low += (left["matched"] if left else 0) - (right["matched"] if right else 1)
        high += (left["matched"] if left else 1) - (right["matched"] if right else 0)
    return [low, high]


def audit(packets, delivered):
    scored = trial.read(RUN / "SCORED_ROWS.json")
    outcome = {"successful_effects": Counter(), "group_rejections": Counter(),
               "invalid_envelopes": {arm: Counter() for arm in ARMS},
               "draft_segments": Counter(), "historical_intersection": {}}
    for key, packet in packets.items():
        draft = packet["candidates"][packet["default_id"]]
        outcome["draft_segments"].update(unit["kind"] for unit in packet["draft_units"])
        for arm in ARMS:
            rec = delivered[key][arm]
            score = scored[key][arm]
            answer = rec["answer"]
            if (sha(answer) if answer is not None else None) != score["answer_sha256"]:
                raise ValueError("Locked decision output changed")
            effects = rec["diagnostics"] or {}
            if rec["error"]:
                outcome["invalid_envelopes"][arm].update([rec["error"]])
            if effects.get("applied_effects"):
                outcome["successful_effects"].update(effects["applied_effects"])
            if effects.get("rejected_groups"):
                outcome["group_rejections"].update(effects["rejected_groups"])
            if rec["status"] in ("KEEP", "GROUP_FALLBACK", "INVALID_EDIT") and answer != draft:
                raise ValueError("A fallback changed the original V1 answer")
    for subset, data in (("historical", [r for r in scored.values() if r["historical"]]),
                         ("all", list(scored.values()))):
        outcome[subset + "_bounds"] = {f"{arm}_minus_{ref}": delta_bounds(data, arm, ref)
                                         for arm, ref in (("DELTA", "FREE"), ("DELTA", "V1"), ("FREE", "V1"))}
    intersection = [r for r in scored.values() if r["historical"] and all(r["grade"][m] for m in ARMS)]
    for arm in ARMS:
        changes = [r["grade"][arm]["matched"] - r["grade"]["V1"]["matched"] for r in intersection]
        outcome["historical_intersection"][arm] = {"recoveries": changes.count(1),
                                                    "regressions": changes.count(-1), "net": sum(changes)}
    trial.probe.freeze(RUN / "AUDIT.json", outcome)
    return outcome


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    command = parser.parse_args().action
    packets, binding, choices, jobs, pin = assign()
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.ARMS = ARMS
    trial.engine.CAP = CAPS
    RUN.mkdir(parents=True, exist_ok=True)
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if command == "freeze":
            trial.probe.freeze(RUN / "FROZEN.json", pin)
            print(json.dumps(pin, indent=2))
            return
        if pin != trial.read(RUN / "FROZEN.json"):
            raise ValueError("Frozen comparison changed")
        if command == "run" and not (RUN / "LEDGER.json").is_file():
            identity = {"experiment_sha256": sha(pin),
                        "service_reference_sha256": trial.probe.read_reference()[1]}
            if identity["service_reference_sha256"] != trial.read(trial.VETO / "EXECUTION.json")["service_reference_sha256"]:
                raise ValueError("API service identity differs")
            trial.probe.freeze(RUN / "EXECUTION.json", identity)
            ledger = []
            delivered = generate(packets, jobs, identity, ledger)
            graded = trial.measure(packets, binding, delivered, identity, ledger)
            if len(ledger) > sum(CAPS.values()):
                raise ValueError("Physical request cap exceeded")
            trial.probe.freeze(RUN / "LEDGER.json", ledger)
        else:
            delivered = trial.read(RUN / "LOCKED_ANSWERS.json")
            graded = trial.read(RUN / "GRADED_ANSWERS.json")
            ledger = trial.read(RUN / "LEDGER.json")
        summary = trial.summarize(packets, binding, choices, graded, ledger)
        print(json.dumps({"primary": summary, "audit": audit(packets, delivered)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
