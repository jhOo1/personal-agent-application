"""Compare witnessed replacement with ordinary reranking on the same saved answers."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from extend import archived, merge_stage
from qamc.common import sha
from qamc.contextual_match.development import text_request
from run_bridge import MODEL, ROOT, engine, prepare, probe, read
from run_reward import RUN as PARENT, requests as ordinary_requests
from selection import METHODS
from settle_reward import summarize, verify_inputs
from veto import PROMPT, decide

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
STAGE = "ConstraintVeto"


def assignments(original, binding):
    tasks = {}
    for key, packet in original.items():
        default, = (cid for cid, name in binding[key]["order"].items() if name == METHODS[0])
        tasks[key] = {**packet, "default_id": default}
    wires = {(key, "VETO"): text_request(PROMPT, task, MODEL, 8192) for key, task in tasks.items()}
    lock = {"packets_sha256": sha(tasks), "choices_binding_sha256": sha(binding),
            "wires_sha256": sha(list(wires.values())),
            "source_sha256": {name: sha((HERE / name).read_bytes())
                              for name in ("experiment.py", "veto.py", "PROTOCOL.md")},
            "physical_cap": len(wires)}
    return tasks, wires, lock


def dispatch(tasks, wires, lock):
    identity = {"experiment_sha256": sha(lock), "service_reference_sha256": probe.read_reference()[1]}
    probe.freeze(RUN / "EXECUTION.json", identity)
    cache, _ = archived(wires, ROOT)
    cache = {key: record for key, record in cache.items() if RUN.name not in Path(record["archive"]).parts}
    ledger = []
    replies = merge_stage(STAGE, wires, cache, identity, ledger)
    choices = {}
    for (key, name), result in replies.items():
        status, choice = result["status"], None
        if status == "OK":
            try:
                choice, status = decide(result["answer"], tasks[key])
            except (ValueError, TypeError, KeyError, AttributeError):
                status = "INVALID_WITNESS"
        choices[key] = {"choice": choice, "status": status, "request_sha256": sha(wires[key, name])}
    probe.freeze(RUN / "LOCKED_CHOICES.json", choices)
    probe.freeze(RUN / "LEDGER.json", ledger)


def settle(original, binding, wires):
    veto = read(RUN / "LOCKED_CHOICES.json")
    ordinary = read(PARENT / "DIRECT_CHOICES.json")
    base_input = ordinary_requests(original)
    if set(veto) != set(ordinary) or set(veto) != set(original):
        raise ValueError("Original assignment is incomplete")
    choices, statuses = {}, {}
    for key, packet in original.items():
        if (veto[key]["request_sha256"] != sha(wires[key, "VETO"])
                or ordinary[key]["request_sha256"] != sha(base_input[key, "DIRECT"])):
            raise ValueError("Choice does not match request")
        arms = {"Veto": veto[key], "Direct": ordinary[key]}
        choices[key] = {name: arm["choice"] for name, arm in arms.items()}
        statuses[key] = {name: arm["status"] for name, arm in arms.items()}
        for cid in choices[key].values():
            if cid is not None and sha(packet["candidates"][cid]) != binding[key]["answer_sha256"][cid]:
                raise ValueError("Archived answer drift")
    _, _, _, _, scores, _, _, _ = prepare()
    previous = read(RUN.with_name("rpe_single_endpoint_bridge_v1") / "RESULTS.json")
    result, detail = summarize(["Direct", "Veto"], choices, statuses, binding, scores, previous)
    signs = {1: "wins", -1: "losses", 0: "ties"}
    result["veto_vs_direct"] = Counter(
        signs[row["scores"]["Veto"]["matched"] - row["scores"]["Direct"]["matched"]]
        for row in detail.values() if row["historical_overlap"]
    )
    ledger = read(RUN / "LEDGER.json")
    tokens = [(row.get("usage") or {}).get("total_tokens") for row in ledger]
    result["cloud"] = {"requests": len(ledger), "reported_tokens": sum(t or 0 for t in tokens),
                       "unknown_usage": tokens.count(None), "statuses": Counter(r["status"] for r in ledger),
                       "automatic_retries": sum(r.get("automatic_retries", 0) for r in ledger)}
    probe.freeze(RUN / "SCORED_ROWS.json", detail)
    probe.freeze(RUN / "SUMMARY.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    arg = ArgumentParser(description=__doc__)
    arg.add_argument("action", choices=("freeze", "run", "report"))
    action = arg.parse_args().action
    original, binding = verify_inputs()
    tasks, wires, lock = assignments(original, binding)
    RUN.mkdir(parents=True, exist_ok=True)
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {STAGE: len(wires)}
    with probe.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            probe.freeze(RUN / "FROZEN.json", lock)
            print(json.dumps(lock, indent=2))
            return
        if read(RUN / "FROZEN.json") != lock:
            raise ValueError("Frozen inputs or code changed")
        if action == "run":
            dispatch(tasks, wires, lock)
        settle(original, binding, wires)


if __name__ == "__main__":
    main()
