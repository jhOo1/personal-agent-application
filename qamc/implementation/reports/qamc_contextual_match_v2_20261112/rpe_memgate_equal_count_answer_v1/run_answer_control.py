"""Execute the frozen, equal-cardinality language comparison on the shared RP Actor."""
import argparse
from collections import Counter
import json
from pathlib import Path

from complete import engine, probe
from extend import archived, merge_stage
from qamc.common import parse_object, sha
from qamc_rpeval_terminal_judge_sensitivity import inspect

from answer_preflight import ARMS, HERE, ROOT, RUN, RUNS, read
from memgate_rpe_preflight import ENDPOINTS, FORMAL, RP

ACTOR, JUDGE = "EqualCountActor", "EqualCountJudge"


def load_plan():
    plan = read(RUN / "FROZEN.json")
    baseline = read(RUNS / "rpe_memgate_matched_actor_v1/RESULTS.json")
    facts = read(FORMAL / "PUBLIC_TASKS.json")
    preflight = read(HERE / "PREFLIGHT.json")
    pins = {
        "code_sha256": sha((HERE / "answer_preflight.py").read_bytes()),
        "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
        "inputs_sha256": sha({u: facts[u] for u in plan["rows"]}),
        "local_selection_sha256": sha(read(RUNS / "rpe_memgate_language_wide_v1/RESULTS.json")),
        "old_memgate_result_sha256": sha(baseline),
    }
    endpoints = {row["uid"]: row for row in read(ENDPOINTS / "RESULTS.json")["rows"]}
    requests = plan["requests"]
    if (
        plan["pins"] != pins or sha(plan) != preflight["private_plan_sha256"]
        or any(sha(value) != key for key, value in requests.items())
        or len(plan["rows"]) != 24 or len({r["group_id"] for r in plan["rows"].values()}) != 24
        or len(requests) - len(plan["reused_actors"]) != preflight["new_actor_cap"]
    ):
        raise ValueError("Preflight no longer verifies")
    roster = read(FORMAL / "PLAN.json")
    cases = {c["uid"]: c for c in roster["cases"] if c["uid"] in plan["rows"]}
    if roster["protocols"]["grading"]["model"] != "gpt-4.1" or any(
        c["independent_confirmation"] for c in cases.values()
    ):
        raise ValueError("Unexpected benchmark grading or exposure contract")
    identity = {
        "experiment_sha256": sha(plan), "runner_sha256": sha(Path(__file__).read_bytes()),
        "scorer_sha256": sha(Path(engine.__file__).read_bytes()),
        "roster_sha256": sha(roster), "endpoints_sha256": sha(endpoints),
        "service_reference_sha256": probe.read_reference()[1],
        "caps": {ACTOR: preflight["new_actor_cap"], JUDGE: preflight["possible_grades_before_cache"]},
    }
    return plan, roster, cases, endpoints, {r["uid"]: r for r in baseline["rows"]}, identity


def generate(plan, identity, ledger):
    keys = {}
    for uid, row in plan["rows"].items():
        for arm, meta in row["arms"].items():
            keys.setdefault(meta["request_sha256"], (uid, arm))
    jobs = {key: plan["requests"][fp] for fp, key in keys.items()}
    cache = {keys[fp]: record for fp, record in plan["reused_actors"].items()}
    replies = merge_stage(ACTOR, jobs, cache, identity, ledger)
    return {fp: replies[key] for fp, key in keys.items()}


def grade_jobs(plan, roster, cases, actors):
    wires, cache, aliases = {}, {}, {}
    for uid, row in plan["rows"].items():
        for arm, meta in row["arms"].items():
            actor = actors[meta["request_sha256"]]
            if actor["status"] != "OK" or "fixed_score" in actor:
                if "fixed_score" in actor and actor["fixed_uid"] != uid:
                    raise ValueError("Fixed grading receipt assigned to wrong case")
                continue
            wire = engine.rpe_wire(roster, cases[uid], {
                "uid": uid, "actor_status": "OK", "answer": actor["answer"],
            })
            digest = sha(wire)
            aliases[uid, arm] = digest
            wires.setdefault(digest, ((uid, arm), wire))
    receipts, _ = archived({fp: v[1] for fp, v in wires.items()}, ROOT)
    current = RUN.relative_to(ROOT).as_posix() + "/"
    for fp, record in receipts.items():
        if not record["archive"].startswith(current):
            cache[wires[fp][0]] = record
    return wires, cache, aliases


def score(uid, arm, labels, actor, judge):
    if "fixed_score" in actor:
        return actor["fixed_score"], actor["fixed_status"]
    if actor["status"] != "OK":
        return None, actor["status"]
    if judge["status"] != "OK":
        return None, judge["status"]
    try:
        raw = judge["answer"]
        fields, _ = probe.fields(parse_object(raw), len(labels), True)
        observation = inspect(
            {"uid": uid, "method": arm, "answer": actor["answer"], "native_fields": fields,
             "raw_scores": {"RPEvalJudge": raw}},
            labels,
        )
        return {"grade": fields, "flags": observation["flags"] if observation else None}, (
            "OK" if fields.get("match") else "INVALID_MATCH"
        )
    except (KeyError, TypeError, ValueError):
        return None, "INVALID_SCORE"


def run(plan, roster, cases, endpoints, baseline, identity):
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = identity["caps"]
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)
        actors = generate(plan, identity, ledger)
        wires, cache, aliases = grade_jobs(plan, roster, cases, actors)
        replies = merge_stage(JUDGE, {key: wire for key, wire in wires.values()}, cache, identity, ledger)
        results = []
        for uid, item in plan["rows"].items():
            reference = endpoints[uid]
            labels = reference["labels"]
            row = {"uid": uid, "group_id": item["group_id"], "labels": labels,
                   "controls": {**reference["scores"], "DIRECT_ZH": baseline[uid]["scores"]["MEMGATE_RP_ACTOR"]},
                   "arms": {}}
            for arm in ARMS:
                meta = item["arms"][arm]
                actor = actors[meta["request_sha256"]]
                grade = replies[wires[aliases[uid, arm]][0]] if (uid, arm) in aliases else None
                fields, status = score(uid, arm, labels, actor, grade)
                row["arms"][arm] = {**meta, "status": status, "score": fields, "actor": actor, "judge": grade}
            results.append(row)
        probe.freeze(RUN / "RESULTS.json", {"rows": results, "ledger": ledger})
        print(json.dumps({"tasks": len(results), "physical_requests": Counter(r["unit"]["stage"] for r in ledger),
                          "statuses": Counter(x["status"] for row in results for x in row["arms"].values())},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("check", "run"))
    args = cli.parse_args()
    bundle = load_plan()
    identity = bundle[-1]
    print(json.dumps({"caps": identity["caps"], "protocol_sha256": sha(identity)}), flush=True)
    if args.action == "run":
        run(*bundle)
