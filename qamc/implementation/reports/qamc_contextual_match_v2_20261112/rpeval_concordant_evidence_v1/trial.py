"""Test same-count source support by intent-estimator agreement on the exact strong Actor."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
previous = run_path(str(BASE / "strong_wire_pruning_replay_v1" / "run.py"))
archive, engine, grading, probe, sha, prune = (previous[k] for k in ("archive", "engine", "grading", "probe", "sha", "prune"))
RUN = engine.RUN.with_name(HERE.name)
OUT = RUN / "private"
ACTOR = "ConcordantEvidenceActor"
ARMS = ("RANKED", "CONCORDANT")
QUOTAS = {"all_A": 2, "B_only": 1, "contains_C": 5}
ORDER = {"C": 0, "B": 1, "A": 2}


def compile_policy(ids, pair):
    ipe, mle, rank = (pair[k]["policy"] for k in ("IPE_ONLY", "MLE_ONLY", "PAPER_FUSION"))
    if set(ipe + mle + rank) - ORDER.keys() or any(len(s) != len(ids) for s in (ipe, mle, rank)):
        raise ValueError("Estimator and Actor source alignment failed")
    agree = {mid for mid, x, y in zip(ids, ipe, mle, strict=True) if x != "A" and y != "A"}
    ranked = sorted(range(len(ids)), key=lambda i: (ORDER[rank[i]], i))[:len(agree)]
    return {"CONCORDANT": agree, "RANKED": {ids[i] for i in ranked}}


def prepare():
    formal = archive.v41.formal.OUT
    frozen = archive.read(formal / "PLAN.json")
    if any(case["independent_confirmation"] for case in frozen["cases"]):
        raise ValueError("Use only the already exposed formal development roster")
    scope = {case["uid"] for case in frozen["cases"]}
    endpoints = {r["uid"]: r for r in archive.read(BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    ranks = {r["uid"]: r["policies"] for r in archive.read(formal / "RPR_RANK_FUSION_AUDIT_300.json")["rows"]}
    strong = {r["uid"]: r for r in archive.read(formal / "RESULT_ROWS.json")
              if r["method"] == engine.RP and r["actor_status"] == "OK" and r["uid"] in scope}
    count, coverage, groups = Counter(), Counter(), set()
    jobs, cards = {}, {}
    prioritized = {uid: end for uid, end in endpoints.items() if uid in strong and uid in ranks
                   and end["old_route"] == "REUSE_RP"}
    eligible = []
    for uid, end in prioritized.items():
        row = strong[uid]
        original = row["actor_request"]
        if (sha(original) != row["actor_request_sha256"]
                or sha(row["answer"]) != end["scores"]["IPE_C"]["answer_sha256"]
                or ranks[uid]["PAPER_FUSION"]["actor_request_sha256"] != sha(original)):
            raise ValueError("Exact strong request drift")
        packet = json.loads(original["messages"][1]["content"])
        ids = [src["memory_id"] for src in packet["source_evidence"]]
        mapped = "".join(p["policy"] for p in packet["preference_use_policy"])
        if mapped != ranks[uid]["PAPER_FUSION"]["policy"]:
            raise ValueError("Reference policy is not the archived fusion")
        both = compile_policy(ids, ranks[uid])
        kind = "contains_C" if "C" in end["labels"] else "B_only" if "B" in end["labels"] else "all_A"
        coverage[kind + "/verified_history_on"] += 1
        if both["RANKED"] == both["CONCORDANT"]:
            continue
        coverage[kind + "/different_equal_count"] += 1
        eligible.append((uid, end, kind, original, packet, both))
    by_kind = {"all_A": 0, "B_only": 1, "contains_C": 2}
    for uid, endpoint, kind, original, packet, keep in sorted(
        eligible, key=lambda x: (by_kind[x[2]], sha(["equal-count-concordant-sources-v1", x[0]]))
    ):
        group = endpoint["source_group"]
        if group in groups or count[kind] >= QUOTAS[kind]:
            continue
        ids = {s["memory_id"] for s in packet["source_evidence"]}
        for arm in ARMS:
            edited, removed = prune(original, ids - keep[arm])
            if removed != ids - keep[arm]:
                raise ValueError("Could not compile exact source and policy removal")
            jobs[uid, arm] = edited
        cards[uid] = {"uid": uid, "stratum": kind, "group": group, "records": packet["source_evidence"],
                      "labels": dict(zip((s["memory_id"] for s in packet["source_evidence"]), endpoint["labels"], strict=True)),
                      "retained": {arm: sorted(ids) for arm, ids in keep.items()}, "archive": endpoint["scores"]["IPE_C"]}
        count[kind] += 1
        groups.add(group)
    if count != QUOTAS:
        raise ValueError(f"Unable to form the stratified exact contrast: {count}")
    pin = {"cases": [{"uid": u, "stratum": c["stratum"], "group": c["group"],
                      "wires": {a: sha(jobs[u, a]) for a in ARMS}} for u, c in cards.items()],
           "coverage": coverage, "caps": {ACTOR: len(jobs), engine.RPE: len(jobs)},
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "reference": probe.read_reference()[1]}
    return pin, cards, jobs


def execute(pin, cards, jobs, live):
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = pin["caps"]
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["reference"]}
    ledger, reuse = [], {}

    def stage(name, wires, cache=None):
        path = OUT / f"{name}_archive.json"
        if live and not path.is_file():
            known, _ = previous["support"]["prior"]["find_archived"](wires, BASE.parents[1])
            saved = []
            for (uid, arm), item in known.items():
                meta = (BASE.parents[1] / item["archive"]).parent / "visible" / item["archive_unit"] / "record.json"
                ref = archive.read(meta).get("reference_config_sha256") if meta.is_file() else None
                if item["status"] == "OK" and ref != pin["reference"]:
                    item = dict(item, status="ARCHIVED_PROTOCOL_UNVERIFIED", answer=None)
                saved.append([uid, arm, item])
            probe.freeze(path, saved)
        old = {(uid, arm): r for uid, arm, r in archive.read(path)}
        if any(r["request_sha256"] != sha(wires[key]) for key, r in old.items()):
            raise ValueError("Prior receipt mismatch")
        pending = {key: wire for key, wire in wires.items() if key not in old}
        reuse[name] = dict(Counter(r["status"] for r in old.values()))
        return old | (engine.stage(name, pending, identity, live, ledger, cache) if pending else {})

    with probe.runner_lock(RUN / "runner.lock"):
        outputs = []
        for (uid, arm), rec in stage(ACTOR, jobs).items():
            card = cards[uid]
            outputs.append({**{k: card[k] for k in ("uid", "group", "stratum")}, "benchmark": "RPEval",
                            "method": arm, "sources": card["records"], "actor_status": rec["status"],
                            "answer": rec["answer"], "score": None})
        grading(outputs, stage)
        result = {"rows": outputs, "ledger": ledger, "reuse": reuse}
        saved = OUT / "RESULTS.json"
        if live:
            probe.freeze(saved, result)
        elif archive.read(saved) != result:
            raise ValueError("Settlement replay drift")
        print({"calls": len(ledger), "transport": Counter(r["status"] for r in ledger), "reuse": reuse})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "replay"))
    action = parser.parse_args().action
    data = prepare()
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, data[0])
        print({"quota": QUOTAS, "coverage": data[0]["coverage"], "caps": data[0]["caps"]})
    elif archive.read(path) != data[0]:
        raise ValueError("Frozen comparison drift")
    else:
        execute(*data, live=action == "run")
