"""Aggregate exact same-task intersections and retain every assigned outcome."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


METHODS = ("BASE", "FREE", "OPERAND")
DOMAINS = ("RPEval", "BenchPreS", "PersistBench")


def persist_pass(score, track):
    key = "failure_strict_utility" if track == "beneficial_memory_usage" else "failure_release"
    return not score[key]


def metrics(domain, cases, method):
    scores = [(case, case["grades"][method]) for case in cases]
    values = Counter()
    for case, score in scores:
        if domain == "RPEval":
            values.update(match=score["matched"], positions=score["total"],
                          **{tag: score["severity"][tag] for tag in ("OPB", "UPB", "FM")})
        elif domain == "BenchPreS":
            for tag in ("aar", "nonbold", "mr"):
                got, out = score[tag]
                values.update({tag: got, tag + "_possible": out})
            values.update(completeness=score["completeness"])
        else:
            track = case["track"]
            values.update({track + "_allocated": 1, track + "_passes": int(persist_pass(score, track))})
    return dict(values)


def primary(domain, case, method):
    score = case["grades"][method]
    if domain == "RPEval":
        return score["matched"]
    if domain == "BenchPreS":
        return score["nonbold"][0]
    return persist_pass(score, case["track"])


def comparison(domain, cases, methods):
    common = [c for c in cases if all(c["grades"].get(m) is not None for m in methods)]
    left, right = methods[-2:]
    changes = [primary(domain, c, right) - primary(domain, c, left) for c in common]
    return {"common": len(common), "groups": len({c["group"] for c in common}),
            "left_right": [left, right],
            "right_wins": sum(x > 0 for x in changes), "right_losses": sum(x < 0 for x in changes),
            "ties": changes.count(0), "metrics": {m: metrics(domain, common, m) for m in methods}}



def missing_bounds(domain, cases, left, right):
    totals = [0, 0]
    for case in cases:
        base = case["grades"]["BASE"]
        maximum = base["total"] if domain == "RPEval" else base["nonbold"][1] if domain == "BenchPreS" else 1
        for arm, sign in ((left, -1), (right, 1)):
            score = case["grades"][arm]
            if score is not None:
                value = sign * primary(domain, case, arm)
                totals[0] += value
                totals[1] += value
            elif sign < 0:
                totals[0] -= maximum
            else:
                totals[1] += maximum
    return totals


def settle(raw):
    by_domain = defaultdict(list)
    for label, case in raw["cases"].items():
        domain, case_label = label.split("/", 1)
        if domain not in DOMAINS:
            raise ValueError(f"Unexpected benchmark {domain}")
        by_domain[domain].append({**case, "grades": {**case["references"], **case["grade"]},
                                  "label": case_label})
    output = {}
    for domain, cases in by_domain.items():
        references = sorted({m for c in cases for m in c["references"]})
        output[domain] = {
            "assigned": len(cases), "groups": len({case["group"] for case in cases}),
            "statuses": {m: dict(Counter(c["disposition"][m] for c in cases)) for m in METHODS[1:]},
            "operations": dict(Counter(o for c in cases for o in c["operations"]["OPERAND"])),
            "common_three": comparison(domain, cases, METHODS),
            "primary_delta_bounds": {
                f"{right}_minus_{left}": missing_bounds(domain, cases, left, right)
                for left, right in (("FREE", "OPERAND"), ("BASE", "OPERAND"), ("BASE", "FREE"))
            },
            "matched_base_by_arm": {m: comparison(domain, cases, ("BASE", m)) for m in METHODS[1:]},
            "matched_reference": {ref: comparison(domain, cases, (ref, "OPERAND")) for ref in references},
        }
    return {"benchmark": output, "cost": raw["cost"]}


if __name__ == "__main__":
    source = Path(sys.argv[1])
    print(json.dumps(settle(json.loads(source.read_text())), indent=2, ensure_ascii=False))
