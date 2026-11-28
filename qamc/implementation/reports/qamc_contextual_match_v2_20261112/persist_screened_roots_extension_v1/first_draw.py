"""Score the fixed policy on ten previously screened development sources."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "persist_frozen_utility_review_v1"))

from check_exposure_fr3 import judge_wire
from complete import ROOT, actor_request, engine, probe, read, select
import extend
from qamc.common import sha
from transfer_replay import persist
from verify_screened import RUN, prepare

POLICIES = ("SELECTED", "GROUP", "FULL", "EMPTY", "RUBRIC")
PRIVATE = RUN / "private"
CAP = {"FixedRouteSelection": 10, "ExtensionActor": 40, "ExtensionJudge": 40}


def grade(raw, track):
    if not raw:
        return None
    try:
        return persist.author.ext.parent.persist.score(track, raw)["rating"]
    except (ValueError, KeyError, TypeError):
        return None


def summarize(rows):
    totals, paired = defaultdict(lambda: defaultdict(Counter)), defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        track = row["track"]
        passed = {arm: val == 3 if track == "beneficial_memory_usage" else val < 3
                  for arm, val in row["ratings"].items() if val is not None}
        for arm in POLICIES:
            val = passed.get(arm)
            totals[track][arm]["unknown" if val is None else "pass" if val else "fail"] += 1
            if arm != "SELECTED":
                a, b = passed.get("SELECTED"), val
                paired[track][arm]["unknown" if None in (a, b) else "tie" if a == b else "win" if a else "loss"] += 1
    return {"totals": totals, "paired": paired}


def exact_stage(name, jobs, config, ledger):
    cache, scanned = extend.archived(jobs, ROOT)
    # Prior same-request failures remain accounted for as missing.
    replies = extend.merge_stage(name, jobs, cache, config, ledger)
    return replies, {"exact_cache": len(cache), "journals_scanned": scanned,
                     "cached_status": dict(Counter(row["status"] for row in cache.values()))}


def execute():
    pin, items, protocol, judge, envelopes = prepare()
    if read(RUN / "FROZEN_PREFLIGHT.json") != pin:
        raise ValueError("Frozen screening reconciliation changed")
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    extend.RUN = RUN
    engine.OUT = probe.OUT = PRIVATE
    probe.RUN, engine.CAP = RUN, CAP
    identity = {"experiment_sha256": sha([pin, sha(Path(__file__).read_bytes())]),
                "service_reference_sha256": pin["config_hash"]}
    ledger, cache_report, results = [], {}, []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(PRIVATE / "EXECUTION.json", identity)
        selection, cache_report["selection"] = exact_stage(
            "FixedRouteSelection", {(u, "SELECTED"): row["select"] for u, row in items.items()}, identity, ledger)
        all_wires, grouped, counts = {}, {}, {}
        for uid, row in items.items():
            for arm in ("FULL", "EMPTY", "RUBRIC"):
                all_wires[uid, arm] = row[arm]
            result = selection[uid, "SELECTED"]
            if result["status"] != "OK":
                continue
            try:
                scope = select(row["case"], row["public"], row["route_answer"], result["answer"])
            except (ValueError, KeyError, TypeError):
                continue
            counts[uid] = len(scope)
            grouped[uid] = "FULL" if scope else "EMPTY"
            all_wires[uid, "SELECTED"] = actor_request(row["case"], row["public"]["query"], scope, protocol,
                                                        protocol["prompts"]["gepa"])
        # Canonicalize within a task first, then reuse exact receipts or deduplicate the new request.
        distinct, index = {}, {}
        for key, wire in all_wires.items():
            index[key] = distinct.setdefault(sha(wire), key)
        unique = {key: all_wires[key] for key in distinct.values()}
        actors, cache_report["actor"] = exact_stage("ExtensionActor", unique, identity, ledger)
        build_judge = judge_wire({u: r["case"] for u, r in items.items()}, items, judge, envelopes)
        jobs = {key: build_judge(key[0], r["answer"]) for key, r in actors.items() if r["status"] == "OK"}
        ratings, cache_report["judge"] = exact_stage("ExtensionJudge", jobs, identity, ledger)
        for uid, item in items.items():
            track = item["case"]["category"]
            modes = {arm: index.get((uid, arm)) for arm in POLICIES if arm != "GROUP"}
            modes["GROUP"] = index.get((uid, grouped[uid])) if uid in grouped else None
            results.append({"uid": uid, "track": track, "subsets": counts.get(uid),
                            "ratings": {arm: grade(ratings.get(key, {}).get("answer"), track)
                                        for arm, key in modes.items()},
                            "actor_status": {arm: actors.get(key, {}).get("status", "UNISSUED")
                                             for arm, key in modes.items()}})
        record = {"rows": results, "ledger": ledger, "cache": cache_report, "summary": summarize(results)}
        probe.freeze(PRIVATE / "RESULTS.json", record)
        print(json.dumps({"summary": record["summary"], "requests": len(ledger),
                          "statuses": Counter(r["status"] for r in ledger), "cache": cache_report},
                         sort_keys=True))


if __name__ == "__main__":
    execute()
