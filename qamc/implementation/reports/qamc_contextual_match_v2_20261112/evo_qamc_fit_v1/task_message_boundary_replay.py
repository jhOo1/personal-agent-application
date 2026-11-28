"""Rebuild frozen Actor and grading records without dispatching any requests."""
from argparse import ArgumentParser
from collections import Counter
import json

from task_message_boundary import ARMS, OUT, PRIVATE, grading, metrics, prepare, read, sha
from task_message_boundary_pairs import groups


def stage_receipts(name):
    manifest = PRIVATE / f"{name}_MANIFEST.json"
    registered = {} if not manifest.is_file() else {
        sha(item["request"]): item["request"] for item in read(manifest)["units"]
    }
    records = {}
    for path in sorted((OUT / name / "visible").glob("*/record.json")):
        row = read(path)
        digest = row["request_sha256"]
        if digest in records or read(path.with_name("request.json")) != registered[digest]:
            raise ValueError("Artifact disagrees with its registered wire")
        if row["status"] == "PENDING_DELIVERY_UNKNOWN":
            continue
        answer = read(path.with_name("response.json"))["answer"] if row["status"] == "OK" else None
        records[digest] = {"status": row["status"], "request_sha256": digest, "answer": answer}
    return registered, records


def replay(cards, jobs, selected, domains, strict):
    stage_cache = {}

    def recover(stage, wires, cache=None):
        if stage not in stage_cache:
            stage_cache[stage] = stage_receipts(stage)
        registered, records = stage_cache[stage]
        matches = {}
        for key, wire in wires.items():
            digest = sha(wire)
            if cache is not None and digest in cache:
                receipt = {"status": "OK", "request_sha256": digest, "answer": cache[digest]}
            elif digest in records:
                receipt = records[digest]
            elif strict or (registered and digest not in registered):
                raise ValueError(f"Missing expected receipt in {stage}")
            else:
                receipt = {"status": "NOT_TERMINAL", "request_sha256": digest, "answer": None}
            matches[key] = receipt
        return matches

    answers = recover("BoundaryActor", jobs)
    rows = []
    for uid, card in cards.items():
        for arm in ARMS:
            receipt = answers.get((uid, arm), {})
            row = {"uid": uid, "method": arm, "benchmark": card["domain"], "stratum": card["stratum"],
                   "sources": card["payload"]["source_evidence"],
                   "actor_status": receipt.get("status", "INPUT_CAPACITY"),
                   "actor_request_sha256": receipt.get("request_sha256"),
                   "answer": receipt.get("answer"), "score": None, "score_flags": None}
            old = selected[uid]
            if row["actor_status"] == "OK" and row["answer"] == old["answer"]:
                row.update(score=old["score"], score_flags=old.get("score_flags"))
            rows.append(row)
    grading([r for r in rows if r["benchmark"] in domains], recover)
    return rows


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--rpe-only", action="store_true")
    args = parser.parse_args()
    pin, cards, jobs, selected = prepare()
    if pin != read(PRIVATE / "FROZEN.json"):
        raise ValueError("Original freeze no longer matches")
    domains = {"RPEval"} if args.rpe_only else {"RPEval", "BenchPreS", "PersistBench"}
    rows = replay(cards, jobs, selected, domains, strict=not args.rpe_only)
    group_scores = groups({uid: c for uid, c in cards.items() if c["domain"] in domains},
                          {"rows": [r for r in rows if r["benchmark"] in domains]})
    if not args.rpe_only:
        saved = read(PRIVATE / "RESULTS.json")
        keys = ("uid", "method", "actor_status", "actor_request_sha256", "answer", "score", "score_flags")
        normalize = lambda records: sorted([r[k] for k in keys] for r in records)
        if normalize(rows) != normalize(saved["rows"]):
            raise ValueError("Read-only reconstruction disagrees with saved scores")
    print(json.dumps({"verified_settled": not args.rpe_only,
                      "parsed_grades": dict(Counter(row["benchmark"] for row in rows if row["score"] is not None)),
                      "metric_valid_grades": dict(Counter(row["benchmark"] for row in rows
                          if metrics(cards[row["uid"]], row["score"]) is not None)),
                      "groups": group_scores}, indent=2))


if __name__ == "__main__":
    main()
