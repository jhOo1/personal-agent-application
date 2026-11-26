"""Summarize anonymous review ratings without exposing private case texts."""
from collections import Counter, defaultdict
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path("runs/qamc_contextual_match_v2_20261112") / HERE.name
FIELDS = ("necessary", "deliverable", "optional_preference", "factual_reliability")


def summarize(frozen, mapping, result):
    reviews = result["reviews"]
    if reviews.keys() != mapping.keys() or len(result["ledger"]) != frozen["cap"]:
        raise ValueError("Review allocation differs from the frozen experiment")
    coverage = frozen["coverage"]
    pairs = defaultdict(dict)
    for identifier, entries in mapping.items():
        review = reviews[identifier]
        for ref in entries:
            uid, arm = ref["uid"], ref["arm"]
            if arm in pairs[uid]:
                raise ValueError("Duplicate review for one arm")
            if not coverage[uid][arm]["answer"] or not coverage[uid][arm]["score"]:
                raise ValueError("Review subcohort must have both answer and score")
            pairs[uid][arm] = review["checks"]
    if any(p.keys() != {"ROUTED", "FULL"} for p in pairs.values()):
        raise ValueError("Review input does not contain an intact pair")
    arms = ("ROUTED", "FULL")
    transitions, states = {}, defaultdict(dict)
    complete = [p for p in pairs.values() if all(p[a] is not None for a in arms)]
    for field in FIELDS:
        transitions[field] = Counter(
            f"{p['ROUTED'][field]['status']}/{p['FULL'][field]['status']}" for p in complete)
        for arm in arms:
            states[arm][field] = Counter(
                p[arm][field]["status"] if p[arm] is not None else "UNAVAILABLE"
                for p in pairs.values())
    ledger = result["ledger"]
    if any(r["automatic_retries"] != 0 for r in ledger):
        raise ValueError("Unexpected review retry")
    return {
        "planned_tasks": len(coverage),
        "routed_and_full_answers_with_native_scores": {
            arm: sum(v[arm]["answer"] and v[arm]["score"] for v in coverage.values())
            for arm in arms},
        "allocated_pairs": len(pairs),
        "complete_review_pairs": len(complete),
        "review_statuses": Counter(r["status"] for r in reviews.values()),
        "review_request_statuses": Counter(r["status"] for r in ledger),
        "request_errors": Counter(r.get("error") or "UNKNOWN" for r in ledger if r["status"] != "OK"),
        "per_arm_check_status": states,
        "paired_check_status_routed_then_full": transitions,
        "observed_necessary_losses": transitions["necessary"]["VIOLATED/MET"],
        "observed_necessary_gains": transitions["necessary"]["MET/VIOLATED"],
        "physical_review_requests": len(ledger),
        "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in ledger),
        "unknown_usage": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger),
        "new_actor_requests": 0,
        "new_native_scores": 0,
        "independent_human_reviewers": 0,
    }


if __name__ == "__main__":
    args = [json.loads((RUN / name).read_text())
            for name in ("FROZEN.json", "PRIVATE_MAPPING.json", "RESULTS.json")]
    print(json.dumps(summarize(*args), indent=2, sort_keys=True))
