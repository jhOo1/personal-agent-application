"""Execute the frozen one-slot experiment on the original shared RP Actor."""
import argparse
from collections import Counter
import json
from pathlib import Path

from complete import engine, probe
from extend import archived, merge_stage
from memgate_rpe_preflight import ENDPOINTS, FORMAL
from qamc.common import sha
from reservation_preflight import ARMS, HERE, ROOT, RUN, read
from run_answer_control import ACTOR, JUDGE, generate, score


def prepare():
    plan = read(RUN / "ANSWER_PRIVATE.json")
    summary = read(HERE / "PREFLIGHT.json")
    pins = plan["pins"]
    manifest = read(FORMAL / "PLAN.json")
    endpoints = {row["uid"]: row for row in read(ENDPOINTS / "RESULTS.json")["rows"]}
    cases = {c["uid"]: c for c in manifest["cases"] if c["uid"] in plan["rows"]}
    if (
        len(cases) != summary["triggered_tasks"] or sha(plan) != summary["private_plan_sha256"]
        or pins["endpoints_sha256"] != sha(endpoints)
        or pins["selection_sha256"] != sha(read(RUN / "SELECTION_PRIVATE.json"))
        or pins["protocol_sha256"] != sha((HERE / "ANSWER_PROTOCOL.md").read_bytes())
        or pins["preflight_code_sha256"] != sha((HERE / "reservation_preflight.py").read_bytes())
        or any(fp != sha(w) for fp, w in plan["requests"].items())
        or any(c["independent_confirmation"] for c in cases.values())
        or manifest["protocols"]["grading"]["model"] != "gpt-4.1"
    ):
        raise ValueError("Frozen reservation inputs changed")
    identity = {"plan_sha256": sha(plan), "runner_sha256": sha(Path(__file__).read_bytes()),
                "shared_engine_sha256": sha(Path(engine.__file__).read_bytes()),
                "manifest_sha256": sha(manifest), "service_reference_sha256": probe.read_reference()[1],
                "caps": {ACTOR: summary["new_actor_cap"], JUDGE: summary["judge_cap"]}}
    return plan, manifest, cases, endpoints, identity


def grading(plan, manifest, cases, actors, identity, ledger):
    wires, assignment = {}, {}
    for uid, item in plan["rows"].items():
        for arm, fields in item["arms"].items():
            actor = actors[fields["request_sha256"]]
            if "fixed_score" in actor:
                if actor["fixed_uid"] != uid:
                    raise ValueError("Attempt to cross-use scoring from another case")
                continue
            if actor["status"] != "OK":
                continue
            wire = engine.rpe_wire(manifest, cases[uid], {
                "uid": uid, "answer": actor["answer"], "actor_status": "OK",
            })
            fp = sha(wire)
            wires.setdefault(fp, ((uid, arm), wire))
            assignment[uid, arm] = wires[fp][0]
    cache_path = RUN / "JUDGE_INPUT_PRIVATE.json"
    jobs = {key: wire for key, wire in wires.values()}
    request_plan_sha = sha(list(wires.values()))
    if cache_path.exists():
        plan_cache = read(cache_path)
        if plan_cache["request_plan_sha256"] != request_plan_sha:
            raise ValueError("The resumed Judge request list changed")
        cache = {wires[fp][0]: record for fp, record in plan_cache["archive"].items()}
    else:
        history, _ = archived({fp: wire for fp, (_, wire) in wires.items()}, ROOT)
        prefix = RUN.relative_to(ROOT).as_posix() + "/"
        history = {fp: record for fp, record in history.items() if not record["archive"].startswith(prefix)}
        probe.freeze(cache_path, {"request_plan_sha256": request_plan_sha, "archive": history})
        cache = {wires[fp][0]: record for fp, record in history.items()}
    replies = merge_stage(JUDGE, jobs, cache, identity, ledger)
    return {key: replies[address] for key, address in assignment.items()}


def run(plan, manifest, cases, endpoints, identity):
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = identity["caps"]
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)
        actors = generate(plan, identity, ledger)
        judges = grading(plan, manifest, cases, actors, identity, ledger)
        rows, statuses = [], Counter()
        for uid, item in plan["rows"].items():
            labels = endpoints[uid]["labels"]
            row = {"uid": uid, "labels": labels, "group_id": item["group_id"],
                   "previous_trial": item["previous_trial"], "controls": endpoints[uid]["scores"], "arms": {}}
            for arm in ARMS:
                selection = item["arms"][arm]
                actor = actors[selection["request_sha256"]]
                judge = judges.get((uid, arm))
                grade, state = score(uid, arm, labels, actor, judge)
                row["arms"][arm] = {**selection, "status": state, "score": grade, "actor": actor, "judge": judge}
                statuses[arm, state] += 1
            rows.append(row)
        probe.freeze(RUN / "RESULTS.json", {"rows": rows, "ledger": ledger})
        print(json.dumps({"tasks": len(rows), "request_stages": Counter(r["unit"]["stage"] for r in ledger),
                          "statuses": {"/".join(k): v for k, v in statuses.items()}}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run"))
    args = parser.parse_args()
    inputs = prepare()
    print(json.dumps({"caps": inputs[-1]["caps"], "protocol_sha256": sha(inputs[-1])}), flush=True)
    if args.action == "run":
        run(*inputs)
