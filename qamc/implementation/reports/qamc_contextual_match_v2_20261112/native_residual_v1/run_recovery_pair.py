"""Compare conditional use to ordinary consideration for saved recovery options."""
from build_jobs import archive_inputs
from pathlib import Path
from optional_recovery import render_recovery
from qamc.common import sha
from run_recovery_proposals import OUT as PROPOSALS
from run_scope_pilot import OUT as PLANS
from scope_visibility import restricted_wire
from trial_reassembly import engine, grading, probe

OUT = PROPOSALS / "pair"
RUN = engine.RUN.with_name("recovery_pair_v1")


def main():
    plans = probe.read(PLANS / "RESULTS.json")
    proposals = probe.read(PROPOSALS / "RESULTS.json")["proposals"]
    originals, cards = archive_inputs()
    jobs = {}
    for uid, candidate in proposals.items():
        if candidate["status"] != "OPTION":
            continue
        key = "RPEval", uid
        row = originals[key]
        original = row["actor_request"]
        if sha(original) != row["actor_request_sha256"]:
            raise ValueError("Original request changed")
        guidance = plans["plans"][uid]
        base, _ = restricted_wire(original, guidance, cards[key]["root"]["original_sources"])
        for arm in ("ordinary", "conditional"):
            jobs[uid, arm] = render_recovery(base, guidance, candidate["option"],
                                             conditional=arm == "conditional")
    cap = len(jobs)
    if not cap:
        print("No accepted options")
        return
    identity = {"experiment_sha256": sha({"jobs": sorted((list(k), sha(v)) for k,v in jobs.items()),
                                           "code": sha(Path(__file__).read_bytes())}),
                "service_reference_sha256": probe.read_reference()[1]}
    OUT.mkdir(exist_ok=True)
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {"RecoveryActor": cap, engine.RPE: cap}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, requests, cache=None):
            return engine.stage(stage, requests, identity, True, ledger, cache) if requests else {}

        rows = []
        for (uid, arm), reply in dispatch("RecoveryActor", jobs).items():
            card = cards["RPEval", uid]
            answer = reply["answer"] if reply["status"] == "OK" else None
            exact = answer == card["base_answer"]
            rows.append({"uid": uid, "method": arm, "benchmark": "RPEval",
                         "group": card["group"], "stratum": card["stratum"],
                         "actor_status": reply["status"], "answer": answer,
                         "sources": card["root"]["original_sources"],
                         "score": card["base_score"] if exact else None,
                         "score_flags": card["base_flags"] if exact else None})
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})
        print(f"Paired candidates: {cap // 2}; recorded requests: {len(ledger)}")


if __name__ == "__main__":
    main()
