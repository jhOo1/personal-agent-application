"""Run the one released-checkpoint comparison, keeping frozen RP and task-only controls."""
import argparse
from collections import Counter
import json
from pathlib import Path

from complete import engine, probe
from extend import archived, merge_stage
from qamc.common import parse_object, sha
from qamc.pa.core import digest
from qamc_rpeval_terminal_judge_sensitivity import inspect

from memgate_rpe_preflight import FORMAL, HERE, ROOT, RP, inputs, read

RUN = engine.RUN.with_name(HERE.name)
ARM, ACTOR, JUDGE = "MEMGATE_RP_ACTOR", "MatchedActor", "MatchedRpeJudge"


def load_plan():
    plan = read(RUN / "PREFLIGHT_PRIVATE.json")
    preflight = read(HERE / "PREFLIGHT.json")
    manifest, _, rp, _, endpoints = inputs()
    pins = plan["pins"]
    expected = {
        "manifest_sha256": digest(manifest), "wires_sha256": sha(plan["requests"]),
        "selection_sha256": sha(plan["selection"]), "endpoint_receipts_sha256": sha(plan["preferred"]),
        "journal_receipts_sha256": sha(plan["cache"]),
        "source_sha256": sha((HERE / "memgate_rpe_preflight.py").read_bytes()),
        "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
    }
    if pins != preflight["pins"] or any(pins[k] != value for k, value in expected.items()):
        raise ValueError("Private preflight does not match frozen fingerprints")
    missing = {entry["request_sha256"] for uid, entry in plan["selection"].items()
               if uid not in plan["preferred"] and entry["request_sha256"] not in plan["cache"]}
    limits = {ACTOR: len(missing),
              JUDGE: len(plan["selection"]) - len(plan["preferred"])}
    if limits[ACTOR] != preflight["distinct_unmatched_actor_wires"]:
        raise ValueError("Physical Actor ceiling differs from the preflight")
    identity = {"preflight_sha256": sha(plan), "runner_sha256": sha(Path(__file__).read_bytes()),
                "score_revision_sha256": sha(Path(engine.__file__).read_bytes()),
                "endpoints_sha256": sha(endpoints), "caps": limits,
                "service_reference_sha256": probe.read_reference()[1]}
    return identity, plan, {r["uid"]: r for r in manifest}, rp, endpoints


def get_actors(plan, identity, ledger):
    wires, cache, preferred = plan["requests"], plan["cache"], plan["preferred"]
    jobs = {(uid, ARM): wires[entry["request_sha256"]]
            for uid, entry in plan["selection"].items() if uid not in preferred}
    reused = {key: cache[sha(wire)] for key, wire in jobs.items() if sha(wire) in cache}
    out = merge_stage(ACTOR, jobs, reused, identity, ledger)
    return {**preferred, **{uid: value for (uid, _), value in out.items()}}


def grade(plan, cases, actors, endpoints, identity, ledger):
    roster = read(FORMAL / "PLAN.json")
    if roster["protocols"]["grading"]["model"] != "gpt-4.1":
        raise ValueError("Expected the historical GPT-4.1 judging contract")
    fixed, jobs = {}, {}
    for uid, receipt in actors.items():
        if receipt["status"] != "OK":
            continue
        shape = plan["selection"][uid]["shape"]
        if shape == "FULL":
            archived = endpoints[uid]["scores"][RP]
        elif shape == "EMPTY" and uid in plan["preferred"]:
            archived = endpoints[uid]["scores"]["TASK_ONLY"]
        else:
            jobs[uid, ARM] = engine.rpe_wire(roster, cases[uid], {
                "uid": uid, "answer": receipt["answer"], "actor_status": "OK",
            })
            continue
        if archived["answer_sha256"] != sha(receipt["answer"]):
            raise ValueError("Fixed endpoint does not verify against the paired score")
        fixed[uid] = {**archived, "origin": "EXACT_FROZEN_ENDPOINT"}
    unique = {sha(wire): wire for wire in jobs.values()}
    archive, _ = archived_score_cache(unique)
    cache = {key: archive[sha(wire)] for key, wire in jobs.items() if sha(wire) in archive}
    responses = merge_stage(JUDGE, jobs, cache, identity, ledger)
    results = []
    for uid in cases:
        old = endpoints[uid]
        cell, response, answer = fixed.get(uid), responses.get((uid, ARM)), actors.get(uid)
        status = plan["missing"].get(uid) or answer["status"]
        if response:
            status = response["status"]
            if status == "OK":
                fields = {}
                try:
                    raw = response["answer"]
                    fields, _ = probe.fields(parse_object(raw), len(old["labels"]), True)
                    report = inspect({"uid": uid, "method": ARM, "answer": answer["answer"],
                                      "native_fields": fields, "raw_scores": {"RPEvalJudge": raw}}, old["labels"])
                    cell = {"grade": fields, "flags": report["flags"] if report else None}
                    if not fields.get("match"):
                        status = "INVALID_MATCH"
                except (KeyError, TypeError, ValueError):
                    cell = {"grade": fields, "flags": None}
                    status = "INVALID_SCORE"
        if cell and not cell["grade"].get("match") and status == "OK":
            status = "INVALID_OR_ABSENT_ARCHIVED_MATCH"
        results.append({"uid": uid, "source_group": old["source_group"], "labels": old["labels"],
                        "scores": {**old["scores"], ARM: cell}, "actor": answer, "judge": response,
                        "status": status, "selection": plan["selection"].get(uid)})
    return results


def archived_score_cache(unique):
    receipts, count = archived(unique, ROOT)
    return {key: row for key, row in receipts.items() if RUN.name not in Path(row["archive"]).parts}, count


def summarize(rows, ledger):
    summary = Counter()
    for row in rows:
        a, b = row["scores"].get(ARM), row["scores"].get("IPE_C")
        match_a = (a or {}).get("grade", {}).get("match")
        match_b = (b or {}).get("grade", {}).get("match")
        if match_a and match_b:
            summary.update(pairs=1, positions=match_a["positions"],
                           memgate=match_a["matched"], ipe_c=match_b["matched"])
    return {"statuses": Counter(r["status"] for r in rows), "paired": summary,
            "requests": Counter(r["unit"]["stage"] for r in ledger),
            "tokens": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
            "usage_unknown": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run"))
    args = parser.parse_args()
    identity, plan, cases, _, endpoints = load_plan()
    print(json.dumps({"allocated": len(cases), "new_call_ceiling": identity["caps"]}), flush=True)
    if args.action == "run":
        engine.OUT = probe.OUT = probe.RUN = RUN
        engine.CAP = identity["caps"]
        ledger = []
        with probe.runner_lock(RUN / "runner.lock"):
            probe.freeze(RUN / "EXECUTION.json", identity)
            actors = get_actors(plan, identity, ledger)
            rows = grade(plan, cases, actors, endpoints, identity, ledger)
            result = {"rows": rows, "ledger": ledger, "summary": summarize(rows, ledger)}
            probe.freeze(RUN / "RESULTS.json", result)
            print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
