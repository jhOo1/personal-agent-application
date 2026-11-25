"""Rank observed policies separately from their eligibility for deployment."""
from collections import Counter, defaultdict
from fractions import Fraction

from qamc.common import sha
from residual import policy
from summarize_reassembly import aligned, measure

BENCHMARKS = ("RPEval", "BenchPreS", "PersistBench")
LOWER_IS_BETTER = ("OPB", "UPB", "FM", "MR")
HIGHER_IS_BETTER = ("completeness", "nonbold", "strict_pass")


def assess(result, baseline):
    rules = policy(result["rules"])
    if not rules:
        raise ValueError("Scientific comparison requires a nonempty policy")
    seen = set()
    gains = defaultdict(list)
    strata = Counter()
    protection = Counter()
    for row in result["rows"]:
        benchmark, uid = row["benchmark"], row["uid"]
        key = benchmark, uid
        if key in seen:
            raise ValueError("Duplicate candidate result")
        seen.add(key)
        original = baseline[key]
        stratum = original["stratum"]
        if (row["group"], row["stratum"]) != (original["group"], stratum):
            raise ValueError("Candidate group or stratum changed")
        base = measure(benchmark, stratum, original["base_score"])
        candidate = measure(benchmark, stratum, row["score"])
        if base is None:
            raise ValueError("Baseline score missing")
        if not aligned({"base": base, "candidate": candidate}, ("base", "candidate")):
            continue
        delta = candidate["primary"] - base["primary"]
        if base["positions"]:
            gains[benchmark].append(Fraction(delta, base["positions"]))
        strata[benchmark, stratum] += delta
        for metric in LOWER_IS_BETTER + HIGHER_IS_BETTER:
            if metric not in base:
                continue
            sign = 1 if metric in LOWER_IS_BETTER else -1
            if (candidate[metric] - base[metric]) * sign > 0:
                protection[benchmark, metric] += 1
    complete = seen == set(baseline) and all(
        row["score"] is not None and measure(row["benchmark"], row["stratum"], row["score"]) is not None
        for row in result["rows"]
    )
    if not complete or any(not gains[name] for name in BENCHMARKS):
        return None
    by_domain = tuple(sum(gains[name]) / len(gains[name]) for name in BENCHMARKS)
    return {"rules": rules, "gains": by_domain, "protection": sum(protection.values()),
            "regressing_strata": sum(value < 0 for value in strata.values()),
            "digest": sha(rules)}


def pick(results, baseline):
    ranked = [candidate for result in results if (candidate := assess(result, baseline))]
    ranked.sort(key=lambda item: (item["regressing_strata"], item["protection"], -sum(item["gains"]),
                                  -min(item["gains"]), len("".join(item["rules"])), item["digest"]))
    scientific = ranked[0] if ranked else None
    deployable = next((item for item in ranked
                       if not item["protection"] and not item["regressing_strata"]
                       and all(gain >= 0 for gain in item["gains"])
                       and sum(gain > 0 for gain in item["gains"]) >= 2), None)
    return {"best_nonempty": scientific, "deployable": deployable}
