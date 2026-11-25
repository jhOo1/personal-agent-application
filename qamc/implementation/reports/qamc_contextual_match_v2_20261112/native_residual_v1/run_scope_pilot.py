"""Shared-plan scope annotation ablation on six exposed RPEval roots."""
import argparse
from pathlib import Path

from build_jobs import archive_inputs, prepare
from qamc.common import sha
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from scope_contract import render
from scope_planner import request, resolve
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "scope_pilot_v1"
RUN = engine.RUN.with_name("nro_scope_pilot_v1")
ARMS = ("unbound", "scoped")


def main(action):
    selected, baselines = prepare(("Keep explicit requirements.",), "search")
    archived, _ = archive_inputs()
    cards = {uid: baselines[domain, uid] for domain, uid in selected if domain == "RPEval"}
    if len(cards) != 6:
        raise ValueError("Expected six frozen RPEval roots")
    originals = {}
    planners = {}
    for uid, card in cards.items():
        item = archived["RPEval", uid]
        originals[uid] = wire = item["actor_request"]
        if sha(wire) != item["actor_request_sha256"]:
            raise ValueError("Original request drift")
        planners[uid, "shared"] = request(wire, card["root"])[0]

    settings = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha({
            "planner_requests": sorted((list(k), sha(v)) for k, v in planners.items()),
            "originals": {uid: sha(wire) for uid, wire in originals.items()},
            "code": {name: sha((HERE / name).read_bytes()) for name in (
                "run_scope_pilot.py", "scope_planner.py", "scope_contract.py", "build_jobs.py")},
        }),
    }
    if action == "check":
        print("6 shared plans, at most 12 Actor and 12 Judge requests")
        return

    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {"ScopePlan": 6, "ScopeActor": 12, engine.RPE: 12}
    ledger = []
    live = action == "run"
    OUT.mkdir(exist_ok=True)
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", settings)
        elif probe.read(OUT / "EXECUTION.json") != settings:
            raise ValueError("Scope execution identity changed")

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, settings, live, ledger, cache) if jobs else {}

        responses = dispatch("ScopePlan", planners)
        actor_jobs, rejected, plans = {}, {}, {}
        for (uid, _), response in responses.items():
            if response["status"] != "OK":
                rejected[uid] = response["status"]
                continue
            try:
                guidance = resolve(response["answer"], originals[uid], cards[uid]["root"])
                planned = {
                    arm: render(originals[uid], guidance, scoped=arm == "scoped")
                    for arm in ARMS
                }
                if max(token_estimate(canonical(v["messages"])) for v in planned.values()) > 32768:
                    raise ValueError("Actor input capacity exceeded")
            except (KeyError, TypeError, ValueError, AttributeError) as error:
                rejected[uid] = type(error).__name__
                continue
            plans[uid] = guidance
            for arm, wire in planned.items():
                actor_jobs[uid, arm] = wire

        answers = dispatch("ScopeActor", actor_jobs)
        rows = []
        for uid, base in cards.items():
            for arm in ARMS:
                reply = answers.get((uid, arm), {})
                status = reply.get("status", "NO_VALID_PLAN")
                answer = reply.get("answer") if status == "OK" else None
                exact = answer == base["base_answer"]
                rows.append({
                    "uid": uid, "benchmark": "RPEval", "group": base["group"],
                    "stratum": base["stratum"], "method": arm, "answer": answer,
                    "actor_status": status, "sources": base["root"]["original_sources"],
                    "score": base["base_score"] if exact else None,
                    "score_flags": base["base_flags"] if exact else None,
                })
        grading(rows, dispatch)
        output = {"rows": rows, "ledger": ledger, "rejected_plans": rejected, "plans": plans}
        if live:
            probe.freeze(OUT / "RESULTS.json", output)
        elif probe.read(OUT / "RESULTS.json") != output:
            raise ValueError("Scope replay differs")
        print(f"Valid plans: {len(plans)}; scored rows: {sum(bool(r['score']) for r in rows)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("check", "run", "replay"))
    main(ap.parse_args().action)
