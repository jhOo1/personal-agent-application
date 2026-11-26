"""Reaggregate archived RPEval grades; publish counts and paired diagnostics only."""

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random


ARMS = ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")
REPLICATES = 10_000
SEED = 281126


def grade(row, arm):
    return ((row["scores"][arm] or {}).get("grade") or {})


def positions(row):
    return len(row["labels"])


def matched(row, arm):
    record = grade(row, arm).get("match")
    if record is None:
        return None
    n = positions(row)
    if record["positions"] != n or type(record["matched"]) is not int or not 0 <= record["matched"] <= n:
        raise ValueError("Mismatched scoring denominator")
    return record["matched"]


def clean(row):
    return all(row["scores"][a]["flags"] == [] for a in ARMS)


def uncertainty(clusters):
    rng = Random(SEED)
    n = len(clusters)
    rates = []
    for _ in range(REPLICATES):
        chosen = [clusters[rng.randrange(n)] for _ in range(n)]
        rates.append(sum(x for x, _ in chosen) / sum(k for _, k in chosen))
    rates.sort()
    return [round(100 * rates[i], 3) for i in (249, 9749)]


def outcome(rows, method, reference, metric):
    groups = defaultdict(lambda: [0, 0])
    wins = losses = 0
    for row in rows:
        k = positions(row)
        a, b = (matched(row, x) for x in (method, reference))
        delta, count = (a - b, k) if metric == "micro" else (int(a == k) - int(b == k), 1)
        g = groups[row["source_group"]]
        g[0] += delta
        g[1] += count
        wins += delta > 0
        losses += delta < 0
    aggregates = [groups[key] for key in sorted(groups)]
    group_sizes = [k for _, k in aggregates]
    pos, denom = map(sum, zip(*aggregates))
    leave_one_out = [Fraction(pos - x, denom - k) for x, k in aggregates if k < denom]
    return {
        "delta_count": pos,
        "denominator": denom,
        "delta_pp": round(100 * pos / denom, 3),
        "resampled_source_group_interval_pp": uncertainty(aggregates),
        "equal_source_group_delta_pp": round(100 * float(sum(Fraction(x, k) for x, k in aggregates) / len(groups)), 3),
        "leave_one_group_out_pp": [round(100 * float(x), 3) for x in (min(leave_one_out), max(leave_one_out))],
        "group_count": len(groups),
        "max_group_denominator": max(group_sizes),
        "task_win_loss_tie": [wins, losses, len(rows) - wins - losses],
    }


def missing_bounds(rows, reference, metric):
    lo = hi = 0
    for row in rows:
        k = positions(row)
        limits = []
        for arm in ("IPE_C", reference):
            x = matched(row, arm)
            if metric == "macro":
                limits.append((0, 1) if x is None else (int(x == k),) * 2)
            else:
                limits.append((0, k) if x is None else (x, x))
        lo += limits[0][0] - limits[1][1]
        hi += limits[0][1] - limits[1][0]
    return [lo, hi]


def exact_opportunities(rows):
    counts = Counter()
    for row in rows:
        selected = "RPR_PAPER_FULL" if row["old_route"] == "REUSE_RP" else "TASK_ONLY"
        a, b = row["scores"]["IPE_C"], row["scores"][selected]
        if any(a[key] != b[key] for key in ("answer_sha256", "grade")):
            raise ValueError("Routing output or grade is not the saved selected endpoint")
        k = positions(row)
        empty = matched(row, "TASK_ONLY") == k
        full = matched(row, "RPR_PAPER_FULL") == k
        if empty != full:
            winner = "task_only" if empty else "full_history"
            counts[f"{winner}_uniquely_exact"] += 1
            counts[f"{winner}_uniquely_exact_missed"] += matched(row, "IPE_C") != k
        else:
            counts["both_exact" if empty else "neither_exact"] += 1
    return counts


def summary(rows):
    scores = {}
    for arm in ARMS:
        values = [matched(row, arm) for row in rows]
        full = [grade(row, arm).get("full_match") for row in rows]
        exact = [int(x == positions(row)) for row, x in zip(rows, values)]
        judge = [grade(row, arm).get("Judge") for row in rows]
        scores[arm] = {
            "matched": sum(values),
            "exact_all_positions": sum(exact),
            "full_match_present": sum(x is not None for x in full),
            "full_match_disagreements": sum(f is not None and f != e for f, e in zip(full, exact)),
            "judge_count": sum(x is not None for x in judge),
            "judge_severity_sum": sum(x for x in judge if x is not None),
        }
    return {"tasks": len(rows), "positions": sum(map(positions, rows)), "scores": scores,
            "exact_endpoint_opportunities": exact_opportunities(rows),
            "paired": {reference: {metric: outcome(rows, "IPE_C", reference, metric)
                                   for metric in ("micro", "macro")} for reference in ARMS[1:]}}


def verify_allocated_labels(path, rows):
    formal = path.parent.parent / "rpeval_formal_multi_coverage_v1"
    manifest = json.loads((formal / "MANIFEST_300.json").read_bytes())
    pins = json.loads((formal / "FROZEN_DATA.json").read_bytes())["files"]
    entries = {card["uid"]: card for card in manifest}
    if len(manifest) != len(rows) or entries.keys() != {r["uid"] for r in rows}:
        raise ValueError("Archive and frozen development rosters differ")
    if any(card["independent_confirmation"] is not False for card in manifest):
        raise ValueError("Expected exclusively exposed development sources")
    sources = {}
    for filename in {card["source_file"] for card in manifest}:
        body = (path.parents[3] / filename).read_bytes()
        if sha256(body).hexdigest() != pins[filename]:
            raise ValueError("Author source differs from frozen bytes")
        sources[filename] = json.loads(body)
    missing = 0
    for row in rows:
        card = entries[row["uid"]]
        original = sources[card["source_file"]][card["row_index"]]
        data = json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        labels = original["intent_type"]
        if (sha256(data).hexdigest() != card["native_row_sha256"]
                or row["source_group"] != card["analysis_group_id"]
                or row["labels"] not in (None, labels) or not labels or set(labels) - set("ABC")):
            raise ValueError("Author row, source group or labels differ from freeze")
        if row["labels"] is None:
            if any(grade(row, a).get("match") is not None for a in ARMS):
                raise ValueError("A missing archive label unexpectedly has a valid grade")
            missing += 1
            row["labels"] = labels
    return missing


def report(path):
    raw = path.read_bytes()
    rows = json.loads(raw)["rows"]
    if len(rows) != 300 or len({r["uid"] for r in rows}) != 300:
        raise ValueError("Not the allocated 300-task development panel")
    allocation_only_labels = verify_allocated_labels(path.resolve(), rows)
    common = [r for r in rows if all(matched(r, arm) is not None for arm in ARMS)]
    if len(common) != 274 or sum(map(positions, common)) != 1462:
        raise ValueError("Expected the verified three-arm intersection")
    subsets = {
        "overall": common,
        "all_A": [r for r in common if set(r["labels"]) == {"A"}],
        "only_B": [r for r in common if "B" in r["labels"] and "C" not in r["labels"]],
        "contains_C": [r for r in common if "C" in r["labels"]],
        "unflagged": [r for r in common if clean(r)],
    }
    return {
        "archive_sha256": sha256(raw).hexdigest(),
        "resampling_seed": SEED,
        "resampling_draws": REPLICATES,
        "allocated_tasks": len(rows),
        "allocation_only_labels": allocation_only_labels,
        "allocated_positions": sum(map(positions, rows)),
        "missing_sensitivity_delta_count": {
            reference: {metric: missing_bounds(rows, reference, metric) for metric in ("micro", "macro")}
            for reference in ARMS[1:]
        },
        "subsets": {k: summary(v) for k, v in subsets.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archived_results", type=Path)
    print(json.dumps(report(parser.parse_args().archived_results), indent=2, sort_keys=True))
