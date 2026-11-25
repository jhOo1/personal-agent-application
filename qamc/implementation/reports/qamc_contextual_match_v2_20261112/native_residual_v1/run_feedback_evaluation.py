"""Evaluate the saved proposal pair once on the exposed search split."""
import argparse

from build_jobs import prepare
from nonempty_selection import pick
from qamc.common import sha
import run_nro_comparison as comparison
from trial_reassembly import probe

ROOT = comparison.HERE
OUT = ROOT / "feedback_proposals_v1"
INPUT = OUT / "RESULTS.json"


def main(action):
    parents = probe.read(INPUT)["proposals"]
    rules = {mode: tuple(parents[mode]["rules"]) for mode in ("atomic", "block")
             if parents[mode]["status"] == "OK"}
    if len(rules) != 2:
        raise ValueError("A complete saved proposal pair is required")
    # Namespace these jobs separately without mutating the prior run protocol.
    comparison.HERE = OUT
    for strategy in rules.values():
        jobs, baseline = prepare(strategy, "search")
        if len(jobs) != 17 or len(baseline) != 20:
            raise ValueError("Search roster changed")
    if action == "check":
        print("Two search candidates; maximum 108 physical requests")
        return

    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "proposal_sha256": sha(INPUT.read_bytes()),
        "roster_sha256": sha((ROOT / "ROSTER.json").read_bytes()),
        "caps_per_candidate": comparison.CAPS,
        "code_sha256": {name: sha((ROOT / name).read_bytes()) for name in (
            "run_feedback_evaluation.py", "run_nro_comparison.py", "nonempty_selection.py",
            "build_jobs.py", "evaluate_nro_policy.py", "residual.py", "freeze_roster.py",
        )},
    }
    live = action == "run"
    with probe.runner_lock(comparison.engine.RUN.with_name("nro_feedback_evaluation_v1") / "runner.lock"):
        path = OUT / "EVALUATION_IDENTITY.json"
        if live:
            probe.freeze(path, identity)
        elif probe.read(path) != identity:
            raise ValueError("Feedback evaluation identity drift")

        selected = {}
        for mode, strategy in rules.items():
            result = comparison.score_candidate(
                strategy, "search", f"feedback_{mode}", 0, identity, live,
            )
            choice = pick([result], baseline)
            selected[mode] = {
                key: item is not None for key, item in choice.items()
            }
        verdict_path = OUT / "SEARCH_ELIGIBILITY.json"
        if live:
            probe.freeze(verdict_path, selected)
        elif probe.read(verdict_path) != selected:
            raise ValueError("Eligibility replay drift")
        print(selected, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
