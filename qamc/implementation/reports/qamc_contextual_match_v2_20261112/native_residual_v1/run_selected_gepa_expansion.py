"""Run the frozen PersistBench comparison with ledgered, capped dispatch."""
import argparse
import json

from check_selected_gepa_grading import grading_panel
from persist_grounding_gepa_wires import actor_request, select, transfer
from preflight_selected_gepa import HERE, prepare
from qamc.common import sha
from trial_reassembly import engine, grading, probe

OUT = HERE / "selected_gepa_expansion_v1"
RUN = engine.RUN.with_name(OUT.name)


def run(live):
    items, _ = prepare()
    judge_hashes = grading_panel()
    cases = {c["uid"]: c for c in json.loads(
        (HERE / "SELECTED_GEPA_EXPANSION_PANEL.json").read_text())["cases"]}
    protocol = transfer.read(transfer.ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    gepa = protocol["prompts"]["gepa"]
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = dict.fromkeys(("QueryRoute", "EvidenceSelect", "FinalActor", "PersistNative"), len(items))
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([items, cases, judge_hashes, protocol["protocols"], gepa,
                                    sha((HERE / "run_selected_gepa_expansion.py").read_bytes()), engine.CAP]),
    }
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, live, ledger, cache) if jobs else {}

        def public_input(uid):
            raw = json.loads(items[uid]["grounding"]["messages"][1]["content"])
            return {"query": raw["query"], "memories": [m["text"] for m in raw["memories"]]}

        method = "SELECTED_GEPA"
        routes = dispatch("QueryRoute", {(uid, method): w["query"] for uid, w in items.items()})
        selector_jobs, failures, selected_stage = {}, {}, {}
        for (uid, _), reply in routes.items():
            if reply["status"] != "OK":
                failures[uid] = reply["status"]
                continue
            try:
                route = transfer.confirmation.route.decode(reply["answer"], public_input(uid)["query"])
            except (ValueError, KeyError, TypeError):
                failures[uid] = "INVALID_ROUTE"
                continue
            branch = "style" if route["check_history"] else "grounding"
            selected_stage[uid] = branch
            selector_jobs[uid, method] = items[uid][branch]
        selectors = dispatch("EvidenceSelect", selector_jobs)
        actor_jobs = {}
        for (uid, _), reply in selectors.items():
            if reply["status"] != "OK":
                failures[uid] = reply["status"]
                continue
            public = public_input(uid)
            try:
                evidence = select(cases[uid], public, routes[uid, method]["answer"], reply["answer"])
            except (ValueError, KeyError, TypeError):
                failures[uid] = "INVALID_SELECTION"
                continue
            actor_jobs[uid, method] = actor_request(cases[uid], public["query"], evidence, protocol, gepa)
        actors = dispatch("FinalActor", actor_jobs)
        rows = []
        for uid, case in cases.items():
            reply = actors.get((uid, method), {})
            rows.append({
                "uid": uid, "method": method, "benchmark": "PersistBench",
                "category": case["category"], "group": case["group"], "branch": selected_stage.get(uid),
                "base_score": case["score"], "score": None, "answer": reply.get("answer"),
                "actor_status": reply.get("status", failures.get(uid, "UNISSUED")),
            })
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    args = parser.parse_args()
    if args.action == "check":
        print(f"Verified {len(grading_panel())} panel grading receipts")
    else:
        run(True)
