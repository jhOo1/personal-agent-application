"""Compare witness-based adjudication and ordinary default-aware selection."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from experiment import HERE, MODEL, ROOT, RUN as VETO, assignments, read, engine, probe
from extend import archived, merge_stage
from qamc.common import sha
from qamc.contextual_match.development import text_request
from run_bridge import prepare
from run_reward import RUN as PARENT
from selection import SYSTEM, parse_compare
from settle_reward import summarize, verify_inputs

RUN = VETO.with_name("rpe_default_selection_control_v1")
STAGE = "DefaultSelection"
PROMPT = SYSTEM + """
The packet identifies the original default answer by default_id. Keep the
default if no other candidate is clearly better for the actual requested
deliverable. You may choose any candidate if justified. The output format
remains the same; do not provide an explanation or citations."""


def execute(wires, lock):
    identity = {"experiment_sha256": sha(lock), "service_reference_sha256": probe.read_reference()[1]}
    if identity["service_reference_sha256"] != read(VETO / "EXECUTION.json")["service_reference_sha256"]:
        raise ValueError("Default and evidence comparisons require the same recorded service")
    probe.freeze(RUN / "EXECUTION.json", identity)
    cache, _ = archived(wires, ROOT)
    cache = {key: row for key, row in cache.items() if RUN.name not in Path(row["archive"]).parts}
    ledger = []
    replies = merge_stage(STAGE, wires, cache, identity, ledger)
    choices = {}
    for (key, method), reply in replies.items():
        status, cid = reply["status"], None
        if status == "OK":
            try:
                cid = parse_compare(reply["answer"])
            except (TypeError, ValueError, KeyError):
                status = "INVALID_CHOICE"
        choices[key] = {"status": status, "choice": cid, "request_sha256": sha(wires[key, method])}
    probe.freeze(RUN / "LOCKED_CHOICES.json", choices)
    probe.freeze(RUN / "LEDGER.json", ledger)


def settle(original, selection, binding, wires):
    selector_sets = {"Direct": read(PARENT / "DIRECT_CHOICES.json"),
                     "Veto": read(VETO / "LOCKED_CHOICES.json"),
                     "DefaultAware": selection}
    if any(set(rows) != set(original) for rows in selector_sets.values()):
        raise ValueError("Original assignment is incomplete")
    choices, statuses = {}, {}
    for key, packet in original.items():
        if selection[key]["request_sha256"] != sha(wires[key, "DEFAULT"]):
            raise ValueError("Selected record differs from the frozen request")
        choices[key] = {name: values[key]["choice"] for name, values in selector_sets.items()}
        statuses[key] = {name: values[key]["status"] for name, values in selector_sets.items()}
        for cid in choices[key].values():
            if cid is not None and sha(packet["candidates"][cid]) != binding[key]["answer_sha256"][cid]:
                raise ValueError("Frozen answer drift")
    _, _, _, _, archive, _, _, _ = prepare()
    parent = read(VETO.with_name("rpe_single_endpoint_bridge_v1") / "RESULTS.json")
    report, details = summarize(list(selector_sets), choices, statuses, binding, archive, parent)
    labels = {1: "wins", -1: "losses", 0: "ties"}
    report["veto_vs_default_aware"] = Counter(
        labels[r["scores"]["Veto"]["matched"] - r["scores"]["DefaultAware"]["matched"]]
        for r in details.values() if r["historical_overlap"]
    )
    ledger = read(RUN / "LEDGER.json")
    tokens = [(row.get("usage") or {}).get("total_tokens") for row in ledger]
    report["cloud"] = {"requests": len(ledger), "reported_tokens": sum(v or 0 for v in tokens),
                       "unknown_usage": tokens.count(None), "statuses": Counter(r["status"] for r in ledger),
                       "automatic_retries": sum(r.get("automatic_retries", 0) for r in ledger)}
    probe.freeze(RUN / "SUMMARY.json", report)
    probe.freeze(RUN / "SCORED_ROWS.json", details)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    args = parser.parse_args()
    original, binding = verify_inputs()
    tasks, _, parent_pin = assignments(original, binding)
    if parent_pin != read(VETO / "FROZEN.json") or not (VETO / "SUMMARY.json").is_file():
        raise ValueError("The frozen evidence comparison must settle first")
    wires = {(key, "DEFAULT"): text_request(PROMPT, packet, MODEL, 8192) for key, packet in tasks.items()}
    lock = {"evidence_experiment_sha256": sha(parent_pin), "wires_sha256": sha(list(wires.values())),
            "code_sha256": sha(Path(__file__).read_bytes()), "physical_cap": len(wires)}
    RUN.mkdir(parents=True, exist_ok=True)
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {STAGE: len(wires)}
    with probe.runner_lock(RUN / "runner.lock"):
        if args.action == "freeze":
            probe.freeze(RUN / "FROZEN.json", lock)
            print(json.dumps(lock, indent=2))
            return
        if read(RUN / "FROZEN.json") != lock:
            raise ValueError("This comparison differs from its input freeze")
        if args.action == "run":
            execute(wires, lock)
        settle(original, read(RUN / "LOCKED_CHOICES.json"), binding, wires)


if __name__ == "__main__":
    main()
