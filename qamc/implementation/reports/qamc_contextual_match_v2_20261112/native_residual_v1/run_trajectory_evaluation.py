"""Evaluate the saved feedback proposals on two frozen development panels."""
import argparse
from collections import Counter

from build_jobs import archive_inputs
from freeze_feedback_panel import HERE, PATH
from nonempty_selection import pick
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from residual import actor_wire, policy
from run_trajectory_proposals import OUT as PROPOSALS
from trial_reassembly import engine, grading, probe


def main(action, split):
    panel = probe.read(PATH)
    proposals = probe.read(PROPOSALS / "RESULTS.json")
    rules = {mode: policy(item["rules"]) for mode, item in proposals["proposals"].items()
             if item["status"] == "OK" and item.get("rules")}
    if set(rules) != {"atomic", "block"}:
        raise ValueError("Expected two nonempty policies")
    output = PROPOSALS / split
    run = engine.RUN.with_name(f"nro_trajectory_{split}_v1")
    if split == "group_out":
        search = probe.read(PROPOSALS / "search" / "RESULTS.json")
        if search["rule_sha256"] != sha(rules):
            raise ValueError("Candidate identities differ from search")

    archive, cards = archive_inputs()
    jobs, baseline = {}, {}
    for entry in panel["rows"]:
        if entry["split"] != split:
            continue
        key = entry["benchmark"], entry["uid"]
        raw, card = archive[key], cards[key]
        if (sha(card["base_answer"]), sha(card["base_score"]), card["group"]) != (
                entry["answer_sha256"], entry["grade_sha256"], entry["group"]):
            raise ValueError("Archived baseline drift")
        baseline[key] = card
        for mode, strategy in rules.items():
            wire = actor_wire(raw["actor_request"], entry["actor_sha256"], strategy,
                              history_enabled=True)
            if token_estimate(canonical(wire["messages"])) > 32768:
                raise ValueError("Candidate Actor input exceeds capacity")
            jobs[key[1], mode] = wire
    sizes = Counter(benchmark for benchmark, _ in baseline)
    caps = {"PolicyActor": 24, "RPEvalJudge": 10, "BenchAttrs": 36, "PersistNative": 8}
    if dict(sizes) != {"RPEval": 5, "BenchPreS": 3, "PersistBench": 4} or len(jobs) != 24:
        raise ValueError("Unexpected panel composition")
    identity = {
        "experiment_sha256": sha([panel, rules, sorted((list(k), sha(v)) for k, v in jobs.items()),
                                   caps, sha((HERE / "run_trajectory_evaluation.py").read_bytes())]),
        "service_reference_sha256": probe.read_reference()[1],
    }
    if action == "check":
        print(split, dict(sizes), sum(caps.values()))
        return

    engine.OUT = probe.OUT = output
    probe.RUN, engine.CAP = run, caps
    output.mkdir(exist_ok=True)
    live = action == "run"
    ledger = []
    with probe.runner_lock(run / "runner.lock"):
        if live:
            probe.freeze(output / "EXECUTION.json", identity)
        elif probe.read(output / "EXECUTION.json") != identity:
            raise ValueError("Execution identity drift")

        def dispatch(stage, batch, cache=None):
            return engine.stage(stage, batch, identity, live, ledger, cache) if batch else {}

        replies = dispatch("PolicyActor", jobs)
        rows = []
        for (benchmark, uid), card in baseline.items():
            for mode in rules:
                receipt = replies[uid, mode]
                if receipt.get("request_sha256") != sha(jobs[uid, mode]):
                    raise ValueError("Actor receipt hash mismatch")
                answer = receipt.get("answer") if receipt["status"] == "OK" else None
                same = answer == card["base_answer"]
                rows.append({"uid": uid, "benchmark": benchmark, "method": mode,
                             "group": card["group"], "stratum": card["stratum"],
                             "sources": card["root"]["original_sources"], "answer": answer,
                             "actor_status": receipt["status"], "origin": "POLICY",
                             "score": card["base_score"] if same else None,
                             "score_flags": card["base_flags"] if same else None,
                             "base_score": card["base_score"], "base_flags": card["base_flags"]})
        grading(rows, dispatch)
        eligibility = {}
        for mode, strategy in rules.items():
            verdict = pick([{"rules": strategy, "rows": [row for row in rows
                            if row["method"] == mode]}], baseline)
            eligibility[mode] = {name: item is not None for name, item in verdict.items()}
        result = {"rows": rows, "ledger": ledger, "rule_sha256": sha(rules),
                  "eligibility": eligibility}
        if live:
            probe.freeze(output / "RESULTS.json", result)
        elif probe.read(output / "RESULTS.json") != result:
            raise ValueError("Result replay drift")
        print(eligibility)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    parser.add_argument("split", choices=("search", "group_out"))
    args = parser.parse_args()
    main(args.action, args.split)
