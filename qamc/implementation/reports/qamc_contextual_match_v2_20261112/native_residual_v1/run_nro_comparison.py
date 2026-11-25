"""Run two matched search rounds per arm, then assess frozen winners."""
import argparse
from pathlib import Path

from build_jobs import prepare
from evaluate_nro_policy import evaluate
from qamc.common import sha
from search_protocol import choose, proposal
from trial_reassembly import engine, probe

HERE = Path(__file__).resolve().parent
CAPS = {
    "RPEval_Actor": 6, "BenchPreS_Actor": 4, "PersistBench_Actor": 7,
    "RPEvalJudge": 6, "BenchAttrs": 24, "PersistNative": 7,
}


def by_key(rows):
    return {(row["benchmark"], row["uid"]): row for row in rows}


def score_candidate(rules, split, mode, round_id, identity, live):
    name = f"nro_compare_v1_{mode}_{split}_{round_id}"
    engine.OUT = probe.OUT = HERE / "comparison_v1" / name
    probe.RUN = engine.RUN.with_name(name)
    arm = "nro_" + sha(rules)[:24]
    engine.CAP = {f"{arm}_{stage}": cap for stage, cap in CAPS.items()}
    ledger = []
    scope = {**identity, "experiment_sha256": sha([identity, name, rules])}
    engine.OUT.mkdir(parents=True, exist_ok=True)
    with probe.runner_lock(probe.RUN / "runner.lock"):
        if live:
            probe.freeze(engine.OUT / "EXECUTION.json", scope)
        elif probe.read(engine.OUT / "EXECUTION.json") != scope:
            raise ValueError("Candidate execution identity drift")

        def dispatch(stage, wires, cache=None):
            return engine.stage(stage, wires, scope, live, ledger, cache) if wires else {}

        rows = evaluate(rules, split, dispatch)
        result = {"rules": list(rules), "rows": rows, "ledger": ledger}
        output = engine.OUT / "RESULTS.json"
        if live:
            probe.freeze(output, result)
        elif probe.read(output) != result:
            raise ValueError("Saved candidate differs from replay")
    return result


def main(action):
    root = HERE / "comparison_v1"
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "roster_sha256": sha((HERE / "ROSTER.json").read_bytes()),
        "code_sha256": {name: sha((HERE / name).read_bytes()) for name in (
            "run_nro_comparison.py", "search_protocol.py", "build_jobs.py",
            "evaluate_nro_policy.py", "residual.py", "freeze_roster.py")},
        "caps_per_candidate": CAPS,
        "search_rounds_per_arm": 2,
        "physical_request_ceiling": 6 * sum(CAPS.values()),
    }
    if action == "check":
        for mode in ("atomic", "block"):
            first = proposal((), mode, 0)
            for rules in (first, proposal((), mode, 1), proposal(first, mode, 1)):
                for split in ("search", "confirmation"):
                    jobs, bases = prepare(rules, split)
                    assert len(jobs) == 17 and len(bases) == 20
        print(identity["physical_request_ceiling"])
        return
    live = action == "run"
    root.mkdir(exist_ok=True)
    with probe.runner_lock(engine.RUN.with_name("native_residual_comparison_v1") / "runner.lock"):
        if live:
            probe.freeze(root / "EXECUTION.json", identity)
        elif probe.read(root / "EXECUTION.json") != identity:
            raise ValueError("Comparison identity changed")
        _, base = prepare((), "search")
        anchors = by_key(evaluate((), "search", lambda *args: {}))
        winners = {}
        for mode in ("atomic", "block"):
            incumbent, scores = (), anchors
            for step in range(2):
                rules = proposal(incumbent, mode, step)
                result = score_candidate(rules, "search", mode, step, identity, live)
                if choose(scores, result["rows"], base):
                    incumbent, scores = rules, by_key(result["rows"])
            winners[mode] = list(incumbent)
        # Freeze selection before any confirmation request can be dispatched.
        if live:
            probe.freeze(root / "WINNERS.json", winners)
        elif probe.read(root / "WINNERS.json") != winners:
            raise ValueError("Winner replay drift")
        for mode, rules in winners.items():
            score_candidate(tuple(rules), "confirmation", mode, 0, identity, live)
        print(winners, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
