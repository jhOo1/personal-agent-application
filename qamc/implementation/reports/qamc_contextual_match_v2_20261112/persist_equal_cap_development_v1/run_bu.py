"""Matched-cap utility comparison under four coupled memory-exposure policies."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

from complete import AUTHOR, BASE, engine, normalized, probe, read
from qamc.common import sha

HERE = Path(__file__).resolve().parent
PRIOR = BASE / "persist_repeated_deployment_v1"
RUN = engine.RUN.with_name(HERE.name)
BU = "beneficial_memory_usage"
METHODS = ("ROUTED", "GROUNDING", "EMPTY", "FULL")
STAGES = {"Route": 1, "Select": 2, "Actor": 4, "Judge": 4}
SOURCES = ("selected_gepa_expansion_v1", "persist_performance_v1")


def prepare():
    api = run_path(str(PRIOR / "run.py"))
    prior_pin, _, _, factorial, judge_protocol, bounds = api["prepare"]()
    old_run = api["RUN"]
    if prior_pin != read(old_run / "FROZEN.json"):
        raise ValueError("Prior roster drift")
    plan = read(AUTHOR.parent / "PLAN.json")
    all_cases = {c["uid"]: c for c in plan["cases"] if c["role"] == "DEV"}
    primary = {uid for uid, category in prior_pin["cases"].items() if category == BU}
    if len(primary) != 6:
        raise ValueError("Original utility slots changed")
    # Require evidence that the archived Style selector was actually dispatched.
    style_ids = set()
    for origin in (*[BASE / "native_residual_v1" / s for s in SOURCES],
                   old_run.with_name("persist_selected_gepa_completion_v1")):
        selection = read(origin / "EvidenceSelect_MANIFEST.json")["units"]
        for item in selection:
            u = item["unit"]
            if u["method"] == "SELECTED_GEPA" and u["root_id"] in all_cases:
                case = all_cases[u["root_id"]]
                if case["category"] != BU:
                    continue
                task = api["persist"].author.parent.smoke.task_for(case)
                public = {"query": task.query, "memories": [x.text for x in task.memories]}
                selector = api["input_requests"](case, public, api["read"](api["transfer"].OUT / "PLAN.json"))
                if item["request"] == selector["style"]:
                    style_ids.add(case["uid"])
    selected, _ = api["load_verified_scores"]()
    occupied = {all_cases[u]["group_id"] for u in primary}
    supplemental = []
    for uid in sorted(style_ids - primary, key=lambda u: sha(["equal-cap-style", u])):
        if uid not in selected or uid not in bounds:
            continue
        group = all_cases[uid]["group_id"]
        if group not in occupied:
            supplemental.append(uid)
            occupied.add(group)
        if len(supplemental) == 6:
            break
    assignments = {uid: "original_utility" for uid in sorted(primary)} | {
        uid: "historical_style" for uid in supplemental}
    cases = {uid: all_cases[uid] for uid in assignments}
    transfer_plan = read(api["transfer"].OUT / "PLAN.json")
    public_inputs, requests = {}, {}
    for uid, case in cases.items():
        task = api["persist"].author.parent.smoke.task_for(case)
        public = {"query": task.query, "memories": [x.text for x in task.memories]}
        if sha(public) != case["public_sha256"]:
            raise ValueError("Utility data changed")
        public_inputs[uid] = public
        requests[uid] = api["input_requests"](case, public, transfer_plan)
        for sources in ([], public["memories"]):
            wire = api["actor_request"](case, public["query"], sources, factorial, factorial["prompts"]["gepa"])
            if wire["max_tokens"] != 8192:
                raise ValueError("Unequal Actor cap")
    pin = {"cohort": assignments, "cap": sum(STAGES.values()) * len(cases),
           "requests": sha(requests), "public_inputs": sha(public_inputs),
           "actor": sha([factorial["protocols"], factorial["prompts"]["gepa"]]),
           "grade_envelopes": sha({uid: bounds[uid] for uid in cases}),
           "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "behavior": sha((HERE / "BEHAVIOR.md").read_bytes()),
           "code": sha(Path(__file__).read_bytes())}
    return pin, api, cases, public_inputs, requests, factorial, judge_protocol, bounds


def execute(pin, api, cases, public, requests, factorial, judge_proto, bounds):
    if pin != read(RUN / "FROZEN.json"):
        raise ValueError("Freeze mismatch")
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = {k: n * len(cases) for k, n in STAGES.items()}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)

        def stage(label, payload):
            return engine.stage(label, payload, identity, True, ledger) if payload else {}

        router = api["transfer"].confirmation.route
        routes = stage("Route", {(u, "ROUTED"): requests[u]["query"] for u in cases})
        branches, bad = {}, {}
        selections = {(u, "GROUNDING"): requests[u]["grounding"] for u in cases}
        for (uid, arm), rec in routes.items():
            if rec["status"] != "OK":
                bad[uid, arm] = rec["status"]
                continue
            try:
                decision = router.decode(rec["answer"], public[uid]["query"])
                branches[uid] = "style" if decision["check_history"] else "grounding"
                selections[uid, arm] = requests[uid][branches[uid]]
            except (ValueError, KeyError, TypeError):
                bad[uid, arm] = "INVALID_ROUTE"
        evidence = {(u, "EMPTY"): [] for u in cases} | {
            (u, "FULL"): public[u]["memories"] for u in cases}
        for (uid, arm), rec in stage("Select", selections).items():
            if rec["status"] != "OK":
                bad[uid, arm] = rec["status"]
                continue
            try:
                if arm == "ROUTED":
                    evidence[uid, arm] = api["select"](cases[uid], public[uid], routes[uid, arm]["answer"], rec["answer"])
                else:
                    memories = public[uid]["memories"]
                    ids = set(api["transfer"].grounding.decode(rec["answer"], len(memories)))
                    evidence[uid, arm] = [value for i, value in enumerate(memories, 1) if f"M{i}" in ids]
            except (ValueError, KeyError, TypeError):
                bad[uid, arm] = "INVALID_SELECTION"
        wires = {(u, a): api["actor_request"](cases[u], public[u]["query"], selected, factorial,
                                              factorial["prompts"]["gepa"])
                 for (u, a), selected in evidence.items()}
        answers = stage("Actor", wires)
        scorer = api["persist"].author.ext.parent.persist
        _, rubrics, formatter = scorer.upstream()
        graders = {}
        for (uid, arm), rec in answers.items():
            if rec["status"] != "OK":
                bad[uid, arm] = rec["status"]
                continue
            data = public[uid]
            wire = api["persist"].author.ext.text_request(
                rubrics[BU], formatter["build_judge_prompt"](data["memories"], data["query"], rec["answer"]),
                judge_proto["model"], judge_proto["stages"][api["persist"].STAGE]["max_tokens"])
            if normalized(wire, rec["answer"]) != bounds[uid]:
                raise ValueError("Scoring envelope changed")
            graders[uid, arm] = wire
        judgments = stage("Judge", graders)
        rows = []
        for uid in cases:
            for arm in METHODS:
                answer = answers.get((uid, arm), {})
                judge = judgments.get((uid, arm), {})
                status, score = bad.get((uid, arm), judge.get("status", "UNISSUED")), None
                if status == "OK":
                    try:
                        score = scorer.score(BU, judge["answer"])
                    except (ValueError, KeyError, TypeError):
                        status = "INVALID_SCORE"
                rows.append({"uid": uid, "arm": arm, "group": pin["cohort"][uid],
                             "branch": branches.get(uid) if arm == "ROUTED" else None,
                             "status": status, "answer": answer.get("answer"), "score": score, "judge": judge,
                             "selection": sha(evidence[uid, arm]) if (uid, arm) in evidence else None,
                             "actor_sha256": answer.get("request_sha256")})
        probe.freeze(RUN / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run"))
    args = parser.parse_args()
    inputs = prepare()
    pin = inputs[0]
    if args.action == "freeze":
        probe.freeze(RUN / "FROZEN.json", pin)
    if args.action == "run":
        execute(*inputs)
    print(json.dumps({"groups": Counter(pin["cohort"].values()), "max_requests": pin["cap"],
                      "freeze_sha256": sha(pin)}))
