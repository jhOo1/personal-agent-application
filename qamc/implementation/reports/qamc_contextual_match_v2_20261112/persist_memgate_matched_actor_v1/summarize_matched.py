"""Summarize completed comparison without exporting private case text or IDs."""
from collections import Counter, defaultdict
import json

from run_matched import BU, RUN, prior_wave, read


def collect(rows, methods):
    outcomes = defaultdict(dict)
    actors = defaultdict(dict)
    for arm, wave, uid, failure, actor_sha in rows:
        if uid in outcomes[arm, wave]:
            raise ValueError("Duplicate result")
        outcomes[arm, wave][uid] = failure
        actors[arm, wave][uid] = actor_sha
    if {a for a, _ in outcomes} != set(methods):
        raise ValueError("Missing method")
    return outcomes, actors


def task_failure(draws):
    if any(draw is True for draw in draws):
        return True
    if None in draws:
        return None
    return False


def compare(candidate, reference):
    paired = [(c, r) for c, r in zip(candidate, reference, strict=True) if c is not None and r is not None]
    wins = sum(not c and r for c, r in paired)
    losses = sum(c and not r for c, r in paired)
    difference = sum(x is True for x in candidate) - sum(x is True for x in reference)
    return {"common": len(paired), "win_loss_tie": [wins, losses, len(paired) - wins - losses],
            "failures_candidate_reference": [sum(c for c, _ in paired), sum(r for _, r in paired)],
            "failure_difference_bounds": [difference - reference.count(None),
                                          difference + candidate.count(None)]}


def main():
    results = read(RUN / "RESULTS.json")
    methods = ("MEMGATE", "ROUTED", "EMPTY", "FULL")
    categories, rows = {}, []
    for rec in results["rows"]:
        categories[rec["uid"]] = rec["category"]
        score = rec["score"]
        key = "failure_strict_utility" if rec["category"] == BU else "failure_release"
        rows.append(("MEMGATE", rec["wave"], rec["uid"], score[key] if score else None,
                     rec["actor"].get("request_sha256")))
    for wave in (0, 1, 2):
        root, _, _ = prior_wave(wave)
        source = root / (f"WAVE{wave}.json" if wave else "RESULTS.json")
        for rec in read(source)["rows"]:
            if rec["arm"] in methods:
                score = rec["score"]
                key = "failure_strict_utility" if wave == 0 else "failure_release"
                rows.append((rec["arm"], wave, rec["uid"], score[key] if score else None, rec["actor_sha256"]))
    outcomes, actors = collect(rows, methods)
    data = {}
    for category in (BU, "sycophancy", "cross_domain"):
        waves = (0,) if category == BU else (1, 2)
        uids = sorted(u for u, track in categories.items() if track == category)
        flags = {arm: [task_failure([outcomes[arm, wave][uid] for wave in waves])
                       for uid in uids] for arm in methods}
        data[category] = {
            "planned": len(uids),
            "failure_pass_missing": {arm: [values.count(v) for v in (True, False, None)]
                                     for arm, values in flags.items()},
            "memgate_vs": {arm: compare(flags["MEMGATE"], flags[arm]) for arm in methods[1:]},
            "same_actor_wire": {arm: sum(bool(actors["MEMGATE", wave][uid]) and
                                         actors["MEMGATE", wave][uid] == actors[arm, wave][uid]
                                         for wave in waves for uid in uids)
                                for arm in methods[1:]},
        }
    status = Counter(r["status"] for r in results["ledger"])
    usage = [r.get("usage") or {} for r in results["ledger"]]
    print(json.dumps({"tracks": data, "logical_result_status": Counter(r["status"] for r in results["rows"]),
                      "actor_provenance": Counter(r["actor"]["origin"] for r in results["rows"]),
                      "physical_requests": len(usage), "physical_status": status,
                      "reported_tokens": sum(u.get("total_tokens") or 0 for u in usage),
                      "unknown_usage": sum(u.get("total_tokens") is None for u in usage),
                      "retries": sum(r.get("automatic_retries", 0) for r in results["ledger"])},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
