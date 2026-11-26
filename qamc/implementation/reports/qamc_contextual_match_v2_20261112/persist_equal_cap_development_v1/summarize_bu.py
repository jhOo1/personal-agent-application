"""Summarize adapted utility scores, honoring within-wave shared requests."""
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path

RUN = Path("runs/qamc_contextual_match_v2_20261112") / Path(__file__).parent.name
METHODS = ("ROUTED", "GROUNDING", "EMPTY", "FULL")


def outcome(row):
    if row["score"] is None:
        return None
    return 0 if not row["score"]["failure_strict_utility"] else 1


def shares_path(left, right):
    a, b = left["actor_sha256"], right["actor_sha256"]
    if a is not None and a == b:
        return True
    return ({left["arm"], right["arm"]} == {"ROUTED", "GROUNDING"}
            and (left["branch"] == "grounding" or right["branch"] == "grounding"))


def compare(rows):
    """Bound failures of the left arm minus failures of the right."""
    count = Counter(assigned=0, known_pairs=0, wins=0, losses=0, ties=0, shared_unknown=0,
                    unrestricted_lower=0, unrestricted_upper=0, coupled_lower=0, coupled_upper=0)
    for left, right in rows:
        a, b = outcome(left), outcome(right)
        count["assigned"] += 1
        if a is not None and b is not None:
            count["known_pairs"] += 1
            count["wins" if a < b else "losses" if a > b else "ties"] += 1
        alo, ahi = (0, 1) if a is None else (a, a)
        blo, bhi = (0, 1) if b is None else (b, b)
        lower, upper = alo - bhi, ahi - blo
        count["unrestricted_lower"] += lower
        count["unrestricted_upper"] += upper
        if shares_path(left, right):
            if (a != b or left["actor_sha256"] != right["actor_sha256"]
                    or left["answer"] != right["answer"] or left["status"] != right["status"]):
                raise ValueError("Coupled methods gave divergent recorded outcomes")
            count["shared_unknown"] += a is None
        else:
            count["coupled_lower"] += lower
            count["coupled_upper"] += upper
    return count


def summarize(plan, result):
    groups = defaultdict(dict)
    for row in result["rows"]:
        uid, arm = row["uid"], row["arm"]
        if row["group"] != plan["cohort"].get(uid) or arm in groups[uid] or arm not in METHODS:
            raise ValueError("Invalid outcome coordinates")
        groups[uid][arm] = row
    if groups.keys() != plan["cohort"].keys() or any(r.keys() != set(METHODS) for r in groups.values()):
        raise ValueError("Incomplete allocation")
    ledger = result["ledger"]
    if len(ledger) > plan["cap"] or any(r.get("automatic_retries") != 0 for r in ledger):
        raise ValueError("Dispatch exceeds frozen contract")
    slices = {"all": list(groups)}
    for uid, name in plan["cohort"].items():
        slices.setdefault(name, []).append(uid)
    methods, pairs = {}, {}
    for name, ids in slices.items():
        methods[name] = {}
        for arm in METHODS:
            rows = [groups[u][arm] for u in ids]
            counts = Counter("UNKNOWN" if outcome(r) is None else
                             "FAIL" if outcome(r) == 1 else "PASS" for r in rows)
            methods[name][arm] = {
                "outcomes": counts, "statuses": Counter(r["status"] for r in rows),
                "available_answers": sum(bool(r["answer"]) for r in rows)}
        pairs[name] = {f"{a}/{b}": compare((groups[u][a], groups[u][b]) for u in ids)
                       for a, b in combinations(METHODS, 2)}
    routed = [group["ROUTED"] for group in groups.values()]
    return {"methods": methods, "pairs": pairs,
            "observed_route_branches": Counter(r["branch"] or "MISSING" for r in routed),
            "physical_calls": len(ledger),
            "physical_stage_calls": Counter(r["unit"]["stage"] for r in ledger),
            "request_statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger)}


if __name__ == "__main__":
    plan = json.loads((RUN / "FROZEN.json").read_text())
    result = json.loads((RUN / "RESULTS.json").read_text())
    print(json.dumps(summarize(plan, result), indent=2, sort_keys=True))
