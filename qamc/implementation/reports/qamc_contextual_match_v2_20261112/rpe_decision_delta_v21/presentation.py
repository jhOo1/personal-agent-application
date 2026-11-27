"""Isolate Markdown marker loss without issuing another generation request."""
from argparse import ArgumentParser
from pathlib import Path
import json
import re

from delta import apply, decode
from qamc.common import sha
import run_delta as delta_run


trial = delta_run.trial
HERE = Path(__file__).resolve().parent
PARENT = delta_run.RUN
RUN = PARENT.with_name("rpe_decision_delta_v21_presentation")
PREFIX = re.compile(r"^ {0,3}(?:[-*+][ \t]+|[0-9]{1,3}[.)][ \t]+|[0-9]{1,3}、[ \t]*)")


def projected(raw, packet):
    plan = decode(raw)
    count = 0
    for group in plan["groups"]:
        for edit in group["edits"]:
            text = edit.get("text")
            if isinstance(text, str) and len(text.splitlines()) == 1:
                clean = PREFIX.sub("", text.strip(), count=1)
                if clean != text.strip():
                    edit["text"] = clean
                    count += 1
    return (apply(json.dumps(plan, ensure_ascii=False), packet, "DELTA"), count) if count else None


def inventory():
    packets, binding, choices, _, parent = delta_run.assign()
    if parent != trial.read(PARENT / "FROZEN.json"):
        raise ValueError("Decision-edit parent drift")
    saved = trial.read(PARENT / "LOCKED_ANSWERS.json")
    if saved.keys() != packets.keys():
        raise ValueError("Incomplete parent answer inventory")
    candidates = {}
    for key, pair in saved.items():
        row = pair["DELTA"]
        diagnostics = row["diagnostics"] or {}
        if "one non-structural line per edit" not in diagnostics.get("rejected_groups", []):
            continue
        canon = projected(row["receipt"]["answer"], packets[key])
        if canon is None:
            continue
        (answer, trace), count = canon
        if answer != row["answer"]:
            candidates[key] = {"DELTA": {"answer": answer, "status": "PRESENTATION_EDIT",
                                         "removed_prefixes": count, "diagnostics": trace}}
    lock = {"parent_freeze": sha(parent), "parent_answers": sha(saved),
            "edited_cases": len(candidates), "projected_output_sha256": sha(candidates),
            "caps": {trial.SCORE_STAGE: len(candidates)},
            "code_sha256": {name: sha((HERE / name).read_bytes()) for name in
                            ("presentation.py", "readouts.sh", "PRESENTATION.md")}}
    return packets, binding, choices, candidates, lock


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    packets, binding, choices, candidates, lock = inventory()
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = RUN
    trial.engine.CAP = lock["caps"]
    RUN.mkdir(parents=True, exist_ok=True)
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            trial.probe.freeze(RUN / "FROZEN.json", lock)
            print(json.dumps(lock, indent=2))
            return
        if lock != trial.read(RUN / "FROZEN.json"):
            raise ValueError("Presentation continuation is not frozen")
        parent = trial.read(PARENT / "GRADED_ANSWERS.json")
        parent_ledger = trial.read(PARENT / "LEDGER.json")
        trial.probe.freeze(RUN / "LOCKED_PRESENTATION_ANSWERS.json", candidates)
        if action == "run" and not (RUN / "LEDGER.json").is_file():
            identity = {"experiment_sha256": sha(lock),
                        "service_reference_sha256": trial.probe.read_reference()[1]}
            if identity["service_reference_sha256"] != trial.read(PARENT / "EXECUTION.json")["service_reference_sha256"]:
                raise ValueError("Presentation grading uses a different service")
            trial.probe.freeze(RUN / "EXECUTION.json", identity)
            ledger = []
            trial.ARMS = ("DELTA",)
            extra = trial.measure({key: packets[key] for key in candidates}, binding, candidates, identity, ledger)
            if len(ledger) > sum(lock["caps"].values()):
                raise ValueError("Presentation cost exceeds the freeze")
            trial.probe.freeze(RUN / "LEDGER.json", ledger)
        else:
            extra = trial.read(RUN / "GRADED_ANSWERS.json")
            ledger = trial.read(RUN / "LEDGER.json")
        if extra.keys() != candidates.keys():
            raise ValueError("Presentation grade inventory differs")
        for key, arms in extra.items():
            parent[key]["DELTA"] = arms["DELTA"]
        trial.ARMS = delta_run.ARMS
        report = trial.summarize(packets, binding, choices, parent, parent_ledger + ledger)
        usage = [(r.get("usage") or {}).get("total_tokens") for r in ledger]
        cost = {"generation_calls": 0, "changed_finals": len(candidates), "scoring_calls": len(ledger),
                "reported_tokens": sum(t or 0 for t in usage), "usage_unknown": usage.count(None)}
        trial.probe.freeze(RUN / "INCREMENTAL_COST.json", cost)
        print(json.dumps({"cost": cost, "composite": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
