"""Generate equal-input proposals from one completed, common search parent."""
import argparse

from build_jobs import prepare
from propose_from_feedback import decode, paired_requests, training_feedback
from qamc.common import sha
from run_nro_comparison import HERE
from trial_reassembly import engine, probe

OUT = HERE / "feedback_proposals_v1"
RUN = engine.RUN.with_name(OUT.name)
PARENT = HERE / "comparison_v1" / "nro_compare_v1_atomic_search_1" / "RESULTS.json"
STAGE = "PolicyProposal"


def main(action):
    parent = probe.read(PARENT)
    jobs, baseline = prepare(parent["rules"], "search")
    feedback = training_feedback(parent, baseline)
    reference = jobs[min(jobs)]
    wires, feedback_digest = paired_requests(parent["rules"], feedback, reference)
    requests = {("shared_parent", mode): wire for mode, wire in wires.items()}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([parent["rules"], feedback_digest, wires]),
                "parent_sha256": sha(PARENT.read_bytes()), "feedback_sha256": feedback_digest}
    if action == "check":
        print(f"Search feedback rows: {len(feedback)}; proposal requests: {len(requests)}")
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {STAGE: 2}
    OUT.mkdir(exist_ok=True)
    live = action == "run"
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif probe.read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Frozen proposal identity changed")
        replies = engine.stage(STAGE, requests, identity, live, ledger)
        proposals = {}
        for (_, mode), response in replies.items():
            result = {"status": response["status"]}
            if response["status"] == "OK":
                try:
                    result["rules"] = list(decode(parent["rules"], mode, response["answer"]))
                except (TypeError, ValueError) as error:
                    result["status"] = "CONTRACT_FAILURE"
                    result["error"] = str(error)
            proposals[mode] = result
        record = {"proposals": proposals, "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", record)
        elif probe.read(OUT / "RESULTS.json") != record:
            raise ValueError("Proposal replay differs")
        print({mode: result["status"] for mode, result in proposals.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
