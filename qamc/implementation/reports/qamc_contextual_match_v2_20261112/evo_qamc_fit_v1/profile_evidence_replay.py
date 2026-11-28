"""Rebuild profile and Actor records, then replay scores without model requests."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from profile_evidence_restoration import (
    ARMS, OUT, PRIVATE, actor_inputs, grading, metrics, parse_profile, prepare, read, sha,
)
from profile_evidence_audit import inspect_stage, user_data
from task_message_boundary_pairs import paired

COMPARISONS = (
    ("PROFILE_AND_QUOTES", "PROFILE"),
    ("PROFILE_AND_QUOTES", "SPECIALIST"),
    ("PROFILE", "SPECIALIST"),
)


def recover_stage(name, requests, cache=None, *, strict=False):
    registered, receipts = inspect_stage(OUT, name)
    keyed = {sha(wire): receipts.get(key, ("NOT_TERMINAL", None)) for key, wire in registered.items()}
    result = {}
    for key, wire in requests.items():
        digest = sha(wire)
        if cache is not None and digest in cache:
            status, answer = "OK", cache[digest]
        else:
            status, answer = keyed.get(digest, ("NOT_TERMINAL", None))
            if (strict or registered) and digest not in keyed:
                raise ValueError(f"Unregistered reconstructed request in {name}")
            if strict and status in {"NOT_TERMINAL", "PENDING_DELIVERY_UNKNOWN"}:
                raise ValueError(f"Unsettled reconstructed request in {name}")
        result[key] = {"status": status, "answer": answer, "request_sha256": digest}
    return result


def replay(cards, requests, refiners, archive, domains, strict):
    cards = {uid: card for uid, card in cards.items() if card["domain"] in domains}
    needed_refiners = {key: request for key, request in refiners.items() if key[0] in cards}
    raw = recover_stage("RefinedProfile", needed_refiners, strict=strict)
    request_state, profiles, actor_jobs = {}, {}, {}
    for uid in cards:
        receipt = raw.get((uid, "PROFILE"))
        if receipt is None:
            request_state[uid] = "EMPTY_INPUT_EXACT_ARCHIVE"
            continue
        request_state[uid] = receipt["status"]
        if receipt["status"] != "OK":
            continue
        history = user_data(requests[uid])["source_evidence"]
        try:
            profiles[uid] = parse_profile(receipt["answer"], history)
        except (ValueError, TypeError, KeyError):
            request_state[uid] = "INVALID_PROFILE_CONTRACT"
            continue
        for arm in ARMS:
            actor_jobs[uid, arm] = actor_inputs(requests[uid], profiles[uid], arm)
    actors = recover_stage("ProfileActor", actor_jobs, strict=strict)
    rows = []
    for uid, card in cards.items():
        for arm in ARMS:
            old = archive[uid]
            reply = actors.get((uid, arm), {})
            if request_state[uid] == "EMPTY_INPUT_EXACT_ARCHIVE":
                reply = {"status": old["actor_status"], "answer": old["answer"],
                         "request_sha256": old["actor_request_sha256"]}
            row = {"uid": uid, "method": arm, "benchmark": card["domain"], "stratum": card["stratum"],
                   "sources": card["payload"]["source_evidence"], "profile_status": request_state[uid],
                   "point_count": len(profiles[uid]) if uid in profiles else None,
                   "actor_status": reply.get("status", "PROFILE_UNAVAILABLE"),
                   "actor_request_sha256": reply.get("request_sha256"), "answer": reply.get("answer"),
                   "score": None, "score_flags": None}
            if row["actor_status"] == "OK" and row["answer"] == old["answer"]:
                row.update(score=old["score"], score_flags=old.get("score_flags"))
            rows.append(row)
    grading(rows, lambda stage, reqs, cache=None: recover_stage(stage, reqs, cache, strict=strict))
    return rows


def aggregate(cards, rows):
    index = {(row["uid"], row["method"]): row for row in rows}
    groups = defaultdict(list)
    for uid in {row["uid"] for row in rows}:
        card = cards[uid]
        values = {arm: metrics(card, index[uid, arm]["score"]) for arm in ARMS}
        values["SPECIALIST"] = metrics(card, card["base_score"])
        flags = {arm: index[uid, arm].get("score_flags") for arm in ARMS}
        flags["SPECIALIST"] = card["base_flags"]
        for key in (card["domain"], card["domain"] + "/" + card["stratum"]):
            groups[key].append((values, flags))
    return {name: {f"{left}_minus_{right}": paired(cases, left, right)
                   for left, right in COMPARISONS} for name, cases in sorted(groups.items())}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=("RPEval", "BenchPreS", "PersistBench"))
    args = parser.parse_args()
    strict = args.domain is None
    domains = {args.domain} if args.domain else {"RPEval", "BenchPreS", "PersistBench"}
    pin, cards, requests, refiners, archive = prepare()
    if read(PRIVATE / "FROZEN.json") != pin:
        raise ValueError("Current experiment freeze does not match")
    rows = replay(cards, requests, refiners, archive, domains, strict)
    if strict:
        saved = read(PRIVATE / "RESULTS.json")
        keys = ("uid", "method", "profile_status", "point_count", "actor_status",
                "actor_request_sha256", "answer", "score", "score_flags")
        normalized = lambda rows: sorted([row[key] for key in keys] for row in rows)
        if normalized(rows) != normalized(saved["rows"]):
            raise ValueError("Score replay diverges from the saved settlement")
    print(json.dumps({"verified_settled": strict,
                      "metric_valid": Counter(r["benchmark"] for r in rows
                                              if metrics(cards[r["uid"]], r["score"]) is not None),
                      "groups": aggregate(cards, rows)}, indent=2))


if __name__ == "__main__":
    main()
