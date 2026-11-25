"""Evaluate matched scope restrictions and archived Gate on 17 exposed roots."""
import argparse
from pathlib import Path

from build_jobs import archive_inputs
from gate_panel import build
from scope_visibility import restricted_wire
from qamc.common import sha
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from scope_contract import render
from scope_planner import request, resolve
from trial_reassembly import archive, engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "scope_gate_v1"
RUN = engine.RUN.with_name("nro_scope_gate_v1")
ARMS = ("unbound", "scoped")


def main(action):
    panel = probe.read(HERE / "GATE_PANEL.json")
    if panel != build():
        raise ValueError("Frozen Gate panel drift")
    archived, baselines = archive_inputs()
    cards = {row["uid"]: baselines["RPEval", row["uid"]] for row in panel["rows"]}
    gate_rows = {row["uid"]: row for row in archive.read(
        archive.v41.formal.OUT / "RESULT_ROWS.json")
        if row["method"] == engine.GATE and row["uid"] in cards}
    for row in panel["rows"]:
        gate = gate_rows[row["uid"]]
        if (sha(gate["answer"]) != row["gate_answer_sha256"] or
                sha(gate["native_fields"]) != row["gate_grade_sha256"]):
            raise ValueError("Archived Gate comparison drift")
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
            "gate_panel": sha(panel),
            "originals": {uid: sha(wire) for uid, wire in originals.items()},
            "code": {name: sha((HERE / name).read_bytes()) for name in (
                "run_gate_scope.py", "scope_planner.py", "scope_contract.py", "scope_visibility.py",
                "build_jobs.py", "gate_panel.py")},
        }),
    }
    if action == "check":
        print("17 shared plans, at most 34 Actor and 34 Judge requests")
        return

    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {"ScopePlan": 17, "ScopeActor": 34, engine.RPE: 34}
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
                # Both arms receive the same visible source set and evidence quotes.
                scoped, _ = restricted_wire(originals[uid], guidance,
                                             cards[uid]["root"]["original_sources"])
                unbound = render(originals[uid], guidance, scoped=False)
                unbound["messages"][-1] = scoped["messages"][-1]
                planned = {"unbound": unbound, "scoped": scoped}
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
        output = {"rows": rows, "ledger": ledger, "rejected_plans": rejected, "plans": plans,
                  "gate_scores": {uid: row["native_fields"] for uid, row in gate_rows.items()}}
        if live:
            probe.freeze(OUT / "RESULTS.json", output)
        elif probe.read(OUT / "RESULTS.json") != output:
            raise ValueError("Scope replay differs")
        print(f"Valid plans: {len(plans)}; scored rows: {sum(bool(r['score']) for r in rows)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("check", "run", "replay"))
    main(ap.parse_args().action)
