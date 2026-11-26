"""Run the frozen PersistBench comparison with ledgered, capped dispatch."""
import argparse
import json

from build_jobs import archive as baseline_archive, archive_inputs
from freeze_persist_performance_panel import build
from transfer_execution import grading_jobs
from transfer_replay import RUNS, persist, saved_scores
from persist_grounding_gepa_wires import actor_request, input_requests, select, smoke, transfer
from preflight_selected_gepa import HERE
from qamc.common import sha
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge
from trial_reassembly import engine, grading, probe

OUT = HERE / "persist_performance_v1"
RUN = engine.RUN.with_name(OUT.name)


def prepare():
    panel = json.loads((HERE / "PERSIST_PERFORMANCE_PANEL.json").read_text())
    if panel != build():
        raise ValueError("Frozen cohort drift")
    archived, _ = archive_inputs()
    sources = smoke.source()
    context, judge_protocol, _ = baseline_archive.transfer.context("PersistBench")
    receipts = saved_scores(RUNS / persist.AUTHOR_OUT.name / "gpt41")
    transfer_plan = transfer.read(transfer.OUT / "PLAN.json")
    cases = {row["uid"]: row for row in panel["cases"]}
    items, judges = {}, {}
    for uid, case in cases.items():
        baseline = archived["PersistBench", uid]
        if (sha(baseline["actor_request"]) != case["actor_request_sha256"]
                or sha(baseline["answer"]) != case["answer_sha256"]):
            raise ValueError(f"Frozen reference drift: {uid}")
        public = smoke.public(sources[case["line"] - 1])
        if sha(public) != case["public_sha256"]:
            raise ValueError(f"Frozen public input drift: {uid}")
        grade, = grading_jobs("PersistBench", [baseline], context, judge_protocol)[0].values()
        receipt = receipts[uid, "PB_RUBRIC"]
        if (sha(grade) != receipt["request_sha256"]
                or baseline["raw_scores"][persist.STAGE] != receipt["response"]["answer"]):
            raise ValueError(f"Frozen Judge drift: {uid}")
        if grade["messages"][1]["content"].count(baseline["answer"]) != 1:
            raise ValueError(f"Ambiguous answer in scoring request: {uid}")
        items[uid] = input_requests(case, public, transfer_plan)
        judges[uid] = sha(grade)
    return items, cases, judges


def run(live):
    items, cases, judge_hashes = prepare()
    protocol = transfer.read(transfer.ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    gepa = protocol["prompts"]["gepa"]
    rubric = PersistAuthorBridge(smoke.UP).blobs["RUBRIC"].decode()
    methods = ("SELECTED_GEPA", "SELECTED_RUBRIC")
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {"QueryRoute": len(items), "EvidenceSelect": len(items),
                  "FinalActor": 2 * len(items), "PersistNative": 2 * len(items)}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([items, cases, judge_hashes, protocol["protocols"], gepa, rubric,
                                    sha((HERE / "run_persist_performance.py").read_bytes()), engine.CAP]),
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
            for variant, template in zip(methods, (gepa, rubric)):
                actor_jobs[uid, variant] = actor_request(
                    cases[uid], public["query"], evidence, protocol, template)
        actors = dispatch("FinalActor", actor_jobs)
        rows = []
        for uid, case in cases.items():
            for variant in methods:
                reply = actors.get((uid, variant), {})
                rows.append({
                    "uid": uid, "method": variant, "benchmark": "PersistBench",
                    "category": case["category"], "group": case["group"],
                    "branch": selected_stage.get(uid), "base_score": case["score"],
                    "score": None, "answer": reply.get("answer"),
                    "actor_status": reply.get("status", failures.get(uid, "UNISSUED")),
                })
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    args = parser.parse_args()
    if args.action == "check":
        print(f"Verified {len(prepare()[2])} panel grading receipts")
    else:
        run(True)
