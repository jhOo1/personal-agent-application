"""Replay established grades from frozen physical receipts without dispatch."""
import argparse
import json

from backbone_behavior_snapshot import snapshot, stable_receipts
from backbone_interface import OUT, grading, prepare, read, sha
from backbone_interface_readout import readout

STAGES = ("RPEvalJudge", "BenchAttrs", "PersistNative")


def read_stage(name):
    path = OUT / "private" / f"{name}_MANIFEST.json"
    if not path.is_file():
        return None, {}
    registration = {sha(item["request"]): item["request"] for item in read(path)["units"]}
    result = {}
    for record in sorted((OUT / name / "visible").glob("*/record.json")):
        row = read(record)
        if row["status"] == "PENDING_DELIVERY_UNKNOWN":
            continue
        digest = row["request_sha256"]
        if digest in result or read(record.with_name("request.json")) != registration[digest]:
            raise ValueError("Judge receipt does not match its registered wire")
        answer = read(record.with_name("response.json"))["answer"] if row["status"] == "OK" else None
        result[digest] = {"status": row["status"], "request_sha256": digest, "answer": answer}
    return registration, result


def replay(pin, roster, jobs, cache, scores, domains):
    if read(OUT / "private" / "FROZEN.json") != pin:
        raise ValueError("Frozen crossover identity changed")
    raw = snapshot(pin, roster, jobs, cache, stable_receipts(pin, jobs))
    original_pools = {item["card"]["uid"]: item["card"]["payload"]["source_evidence"]
                      for item in roster}
    rows, grade_targets = [], []
    for uid, source in raw.items():
        for method, answer in source["arms"].items():
            row = {"uid": uid, "method": method, "benchmark": source["benchmark"],
                   "stratum": source["stratum"], "sources": original_pools[uid],
                   "actor_request_sha256": answer["request_sha256"], "score": None, "score_flags": None,
                   "actor_status": "OK" if answer["answer"] else answer["status"], "answer": answer["answer"]}
            rows.append(row)
            if source["benchmark"] not in domains or not row["answer"]:
                continue
            old = scores.get((uid, sha(row["answer"])))
            if old and old.get("score") is not None:
                row.update(score=old["score"], score_flags=old.get("score_flags"))
            else:
                grade_targets.append(row)

    def stage(name, requests, cached=None):
        if name not in STAGES:
            raise ValueError("Unknown read-only grading stage")
        registration, receipts = read_stage(name)
        archive = cached or {}
        recovered = {}
        for key, wire in requests.items():
            digest = sha(wire)
            if digest in archive:
                recovered[key] = {"status": "OK", "answer": archive[digest], "request_sha256": digest}
            elif digest in receipts:
                recovered[key] = receipts[digest]
            elif registration is not None and digest not in registration:
                raise ValueError(f"Unregistered reconstructed grading wire in {name}")
            else:
                recovered[key] = {"status": "NOT_TERMINAL", "answer": None, "request_sha256": digest}
        return recovered

    grading(grade_targets, stage)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpe-only", action="store_true")
    parser.add_argument("--verify-settled", action="store_true")
    args = parser.parse_args()
    if args.rpe_only and args.verify_settled:
        parser.error("Full settlement verification requires all domains")
    pin, roster, jobs, cache, scores, _ = prepare()
    domains = ("RPEval",) if args.rpe_only else ("RPEval", "BenchPreS", "PersistBench")
    rows = replay(pin, roster, jobs, cache, scores, domains)
    ledger = []
    if args.verify_settled:
        terminal = read(OUT / "RESULTS.json")
        fields = ("uid", "method", "actor_status", "answer", "score", "score_flags")
        records = lambda group: sorted([r[k] for k in fields] for r in group)
        if records(rows) != records(terminal["rows"]):
            raise ValueError("Independent receipt replay disagrees with the settlement")
        ledger = terminal["ledger"]
    stats = readout(roster, rows, ledger)
    stats = {"replayed_domains": domains, "terminal_verified": args.verify_settled,
             "new_model_calls": 0, "sections": stats["sections"],
             "dispatches": stats["dispatches"], "transport": stats["transport"],
             "reported_tokens": stats["tokens"], "unknown_usage": stats["unknown_usage"],
             "pairs": stats["pairwise"], "history_model_score_difference": stats["history_model_score_difference"]}
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
