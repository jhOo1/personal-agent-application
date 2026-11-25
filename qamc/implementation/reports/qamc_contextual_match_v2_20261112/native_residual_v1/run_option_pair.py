"""Run matched ordinary revision and append-only personalization."""
import argparse
from collections import Counter
from pathlib import Path

from build_jobs import archive_inputs, prepare
from option_actor import INSTRUCTIONS, option_request, resolve_option
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "option_pair_v1"
RUN = engine.RUN.with_name("nro_option_pair_v1")


def main(action):
    eligible, cards = prepare(("Validate fixed history eligibility.",), "search")
    wires, _ = archive_inputs()
    jobs = {}
    for key in eligible:
        archive = wires[key]
        wire = archive["actor_request"]
        if sha(wire) != archive["actor_request_sha256"]:
            raise ValueError("Archived request drift")
        for method in INSTRUCTIONS:
            request = option_request(wire, cards[key]["base_answer"], method)
            if token_estimate(canonical(request["messages"])) > 32768:
                raise ValueError("Revision request exceeds capacity")
            jobs[key[1], method] = request

    counts = Counter(benchmark for benchmark, _ in eligible)
    caps = {"OptionActor": len(jobs), "RPEvalJudge": 2 * counts["RPEval"],
            "BenchAttrs": 12 * counts["BenchPreS"], "PersistNative": 2 * counts["PersistBench"]}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha({
            "caps": caps, "roster": sha((HERE / "ROSTER.json").read_bytes()),
            "jobs": sorted((list(key), sha(wire)) for key, wire in jobs.items()),
            "code": {name: sha((HERE / name).read_bytes()) for name in
                     ("run_option_pair.py", "option_actor.py", "frozen_decision.py")},
        }),
    }
    if action == "check":
        print(dict(counts), caps, sum(caps.values()))
        return

    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = caps
    live = action == "run"
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif probe.read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Execution identity drift")

        def dispatch(stage, batch, cache=None):
            return engine.stage(stage, batch, identity, live, ledger, cache) if batch else {}

        replies = dispatch("OptionActor", jobs)
        rows = []
        for (benchmark, uid), card in cards.items():
            original = card["base_answer"]
            for method in INSTRUCTIONS:
                receipt = replies.get((uid, method))
                status, answer = "OK", original
                if receipt is not None:
                    if receipt.get("request_sha256") != sha(jobs[uid, method]):
                        raise ValueError("Revision receipt hash mismatch")
                    status, answer = receipt["status"], None
                    if status == "OK":
                        try:
                            answer = resolve_option(original, receipt["answer"], method)
                        except (ValueError, TypeError):
                            status = "INVALID_REVISION_CONTRACT"
                exact = answer == original
                rows.append({
                    "uid": uid, "benchmark": benchmark, "group": card["group"],
                    "stratum": card["stratum"], "method": method,
                    "actor_status": status, "answer": answer,
                    "sources": card["root"]["original_sources"],
                    "score": card["base_score"] if exact else None,
                    "score_flags": card["base_flags"] if exact else None,
                    "base_score": card["base_score"], "base_flags": card["base_flags"],
                    "origin": "ARCHIVE" if receipt is None else "KEEP" if exact else "REVISION",
                })
        grading(rows, dispatch)
        report = {"rows": rows, "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", report)
        elif probe.read(OUT / "RESULTS.json") != report:
            raise ValueError("Replay mismatch")
        print(f"{len(rows)} rows; {len(ledger)} ledger entries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
