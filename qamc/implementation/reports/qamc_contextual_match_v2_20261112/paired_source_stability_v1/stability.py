"""Paired group-resampled effect estimates from checked exposed benchmark scores."""
from collections import defaultdict
import json
from pathlib import Path
from random import Random
import sys

BASE = Path(__file__).resolve().parent.parent
for directory in ("native_residual_v1", "persist_selected_gepa_completion_v1"):
    sys.path.insert(0, str(BASE / directory))

import audit_bench_raw_common as bench
from compare_controls import load_verified_scores
from complete import AUTHOR, passes

DRAWS = 10000
SEED = 20261126


def read(path):
    return json.loads(path.read_text())


def paired(label, rows):
    """Rows contain (group, candidate numerator, control numerator, shared denominator)."""
    totals = defaultdict(lambda: [0, 0, 0])
    for group, a, b, n in rows:
        if not group or n <= 0:
            raise ValueError("Invalid paired unit")
        for i, value in enumerate((a, b, n)):
            totals[group][i] += value
    groups = [totals[g] for g in sorted(totals)]
    a, b, n = (sum(xs) for xs in zip(*groups, strict=True))
    rng = Random(str(SEED) + label)
    draws = []
    for _ in range(DRAWS):
        sample = rng.choices(groups, k=len(groups))
        diff = sum(l - r for l, r, _ in sample)
        d = sum(denom for _, _, denom in sample)
        draws.append(100 * diff / d)
    draws.sort()
    leave_one = [100 * (a - b - l + r) / (n - denom) for l, r, denom in groups if n > denom]
    return {"tasks": len(rows), "groups": len(groups), "candidate": a, "control": b, "denominator": n,
            "effect_points": 100 * (a - b) / n,
            "group_resampling_95_percentile": [draws[int(.025 * DRAWS)], draws[int(.975 * DRAWS) - 1]],
            "leave_one_group_range": [min(leave_one), max(leave_one)],
            "group_positive_ties_negative": [sum(l > r for l, r, _ in groups),
                                             sum(l == r for l, r, _ in groups),
                                             sum(l < r for l, r, _ in groups)]}


def rpeval():
    result = defaultdict(list)
    rows = read(BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    for row in rows:
        grades = {k: cell["grade"] for k, cell in row["scores"].items()}
        if not all(v.get("match") for v in grades.values()):
            continue
        labels = row["labels"]
        count = len(labels)
        if not count or any(count != grade["match"]["positions"] for grade in grades.values()):
            raise ValueError("RPEval strict denominator changed")
        split = "Contains-C" if "C" in labels else "Only-B" if "B" in labels else "All-A"
        a = grades["IPE_C"]["match"]["matched"]
        for method in ("TASK_ONLY", "RPR_PAPER_FULL"):
            b = grades[method]["match"]["matched"]
            for scope in ("Overall", split):
                result[f"RPEval/{method}/{scope}"].append((row["source_group"], a, b, count))
    return result


def benchpres():
    cases, scores = bench.load_matched_scores()
    result = defaultdict(list)
    for uid, case in cases.items():
        grades = {m: scores[uid, m]["score"] for m in bench.METHODS}
        if not all(grades.values()):
            continue
        primary = grades[bench.GATE]
        allowed = [(x["preference"], x["appropriate"]) for x in primary["decisions"]]
        for method in (bench.SELECTIVITY, "RAW"):
            control = grades[method]
            if allowed != [(x["preference"], x["appropriate"]) for x in control["decisions"]]:
                raise ValueError("BenchPreS attribute order changed")
            for name in ("aar", "mr"):
                d = primary[f"{name}_denominator"]
                if d != control[f"{name}_denominator"]:
                    raise ValueError("BenchPreS denominator changed")
                if d:
                    result[f"BenchPreS/{method}/{name}"].append(
                        (case["analysis_group_id"], primary[f"{name}_numerator"],
                         control[f"{name}_numerator"], d))
            def nonbold(grade):
                return [x for x in grade["decisions"] if x["appropriate"]
                        and not any(t in x["preference"].lower() for t in
                                    ("bold text", "bold formatting", "bold typeface"))]
            a, b = map(nonbold, (primary, control))
            if a:
                result[f"BenchPreS/{method}/nonbold_aar"].append(
                    (case["analysis_group_id"], sum(x["label"] == "follow" for x in a),
                     sum(x["label"] == "follow" for x in b), len(a)))
    return result


def persistbench():
    cases = {row["uid"]: row for row in read(AUTHOR.parent / "PLAN.json")["cases"]}
    selected, controls = load_verified_scores()
    result = defaultdict(list)
    for uid, (track, score) in selected.items():
        case = cases[uid]
        if case["role"] != "DEV" or case["category"] != track:
            raise ValueError("PersistBench development identity changed")
        a = passes(score, track)
        for method in ("PB_RUBRIC", "PB_GEPA", "MEMADAPTER_FULL"):
            if method not in controls[uid]:
                continue
            b = passes(controls[uid][method], track)
            for scope in ("Overall", track):
                result[f"PersistBench/{method}/{scope}"].append((case["group_id"], a, b, 1))
    return result


def audit():
    panels = {**rpeval(), **benchpres(), **persistbench()}
    result = {key: paired(key, rows) for key, rows in panels.items()}
    for key, values in {
        "RPEval/RPR_PAPER_FULL/Overall": (953, 824, 1462),
        "RPEval/TASK_ONLY/Overall": (953, 874, 1462),
        "BenchPreS/PAPER_SELECTIVITY/mr": (1, 12, 126),
        "BenchPreS/PAPER_SELECTIVITY/nonbold_aar": (35, 36, 43),
        "PersistBench/PB_RUBRIC/Overall": (47, 43, 49),
        "PersistBench/MEMADAPTER_FULL/Overall": (46, 37, 48),
    }.items():
        if tuple(result[key][k] for k in ("candidate", "control", "denominator")) != values:
            raise ValueError(f"Published common panel changed: {key}")
    return {"draws": DRAWS, "seed": SEED, "net_signs": "candidate minus control", "new_requests": 0,
            "effects": result}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
