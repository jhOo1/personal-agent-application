"""Replay frozen BenchPreS repeat waves, retaining each pairing and missing denominator."""
import argparse
from collections import Counter, defaultdict
import json
from random import Random
import re

import run_qamc_benchpres_three_draw as run
from qamc.common import sha
from qamc.pa.core import digest


METRICS = ("MR", "AAR", "nonbold_AAR", "completeness")
BOLD = re.compile(r"\bbold\s+text\b", re.I)
SEED = 20261126
BOOTSTRAP_DRAWS = 5000


def sum_metric(values, metric):
    return tuple(sum(v[metric][i] for v in values) for i in range(2))


def ref_counts(reference):
    labels = reference["preference_label"]
    if len(labels) != len(reference["preference_attribute"]) or len(labels) != 5:
        raise ValueError("Expected five aligned author attributes")
    return {"MR": 5 - sum(labels), "AAR": sum(labels),
            "nonbold_AAR": sum(bool(flag) and not BOLD.search(text)
                               for flag, text in zip(labels, reference["preference_attribute"])),
            "completeness": 1}


def metric_values(score, reference):
    labels = reference["preference_label"]
    if [(r["preference"], bool(r["appropriate"])) for r in score["decisions"]] != [
        (text, bool(flag)) for flag, text in zip(labels, reference["preference_attribute"])
    ]:
        raise ValueError("Grade decisions differ from pinned attributes")
    if any(r["label"] not in ("follow", "do_not_follow") for r in score["decisions"]):
        raise ValueError("Grade labels outside the scorer contract")
    counts = ref_counts(reference)
    decisions = score["decisions"]
    values = {
        "MR": sum(not r["appropriate"] and r["label"] == "follow" for r in decisions),
        "AAR": sum(bool(r["appropriate"]) and r["label"] == "follow" for r in decisions),
        "nonbold_AAR": sum(bool(r["appropriate"]) and r["label"] == "follow" and not BOLD.search(r["preference"])
                            for r in decisions),
        "completeness": score["task_completeness"],
    }
    for k in ("MR", "AAR"):
        if (values[k], counts[k]) != (score[k.lower() + "_numerator"], score[k.lower() + "_denominator"]):
            raise ValueError("Original score totals do not replay")
    if type(values["completeness"]) is not int or not 1 <= values["completeness"] <= 5:
        raise ValueError("Invalid original completeness rating")
    return {k: (v, counts[k]) for k, v in values.items()}


def rate(x, d):
    return x / d if d else None


def paired_report(pairs, groups):
    sums = defaultdict(lambda: defaultdict(Counter))
    for left, right, uid in pairs:
        block = sums[groups[uid]]
        for metric in METRICS:
            n, d = left[metric]
            r, rd = right[metric]
            if d != rd:
                raise ValueError("Paired denominators differ")
            block[metric].update(left=n, right=r, denom=d)
    stats = {}
    for metric in METRICS:
        valid = [sums[g][metric] for g in sorted(sums) if sums[g][metric]["denom"]]
        left = sum(x["left"] for x in valid)
        right = sum(x["right"] for x in valid)
        denom = sum(x["denom"] for x in valid)
        interval = None
        if len(valid) >= 2:
            rng = Random(SEED)
            boot = []
            for _ in range(BOOTSTRAP_DRAWS):
                sampled = [valid[rng.randrange(len(valid))] for _ in valid]
                boot.append(sum(x["left"] - x["right"] for x in sampled) / sum(x["denom"] for x in sampled))
            boot.sort()
            interval = [boot[124], boot[4874]]
        stats[metric] = {"gate_numerator": left, "selectivity_numerator": right, "denominator": denom,
                         "gate_minus_selectivity": rate(left - right, denom),
                         "profile_bootstrap_interval": interval, "profile_groups_with_metric": len(valid)}
    return {"task_draw_pairs": len(pairs), "tasks": len({uid for _, _, uid in pairs}), "metrics": stats}


def aggregation(units, scores, refs):
    report = {}
    for method in run.METHODS:
        draw_rows = []
        for rep in run.REPEATS:
            selected = [(uid, arm, draw) for uid, arm, draw in units if method == arm and draw == rep]
            valid = [scores[key] for key in selected if key in scores]
            known_count = len(valid)
            metrics = {}
            for metric in METRICS:
                n, d = sum_metric(valid, metric)
                fixed = sum(ref_counts(refs[uid])[metric] for uid, _, _ in selected)
                lo, hi = (n + fixed - d, n + (fixed - d) * 5) if metric == "completeness" else (n, n + fixed - d)
                metrics[metric] = {"numerator": n, "scored_denominator": d, "fixed_denominator": fixed,
                                   "strict": rate(n, fixed) if known_count == len(selected) else None,
                                   "bounds": [rate(lo, fixed), rate(hi, fixed)]}
            draw_rows.append({"scored_tasks": known_count, "allocated_tasks": len(selected), "metrics": metrics})
        mean = {k: (sum(d["metrics"][k]["strict"] for d in draw_rows) / 3 if
                    all(d["metrics"][k]["strict"] is not None for d in draw_rows) else None) for k in METRICS}
        report[method] = {"draws": draw_rows, "strict_mean_over_draws": mean}
    return report


def replay(plan):
    run.valid(plan)
    if run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"] != sha(plan):
        raise ValueError("Private run plan differs from the committed preflight")
    case_index = {c["uid"]: c for c in plan["cases"]}
    chunks = plan["waves"]
    all_uids = [u for chunk in chunks for u in chunk]
    if set(all_uids) != set(case_index) or len(all_uids) != len(case_index):
        raise ValueError("Frozen waves must partition the intended cases")
    groups = {uid: case["analysis_group_id"] for uid, case in case_index.items()}
    refs = {}
    for uid, case in case_index.items():
        if case["benchmark"] != "benchpres" or case["independent_confirmation"]:
            raise ValueError("Expected exposed BenchPreS cases only")
        ref = run.read(run.ROOT / case["evaluation_path"])
        if digest(ref) != case["evaluation_hash"]:
            raise ValueError("Pinned evaluation data differs")
        refs[uid] = ref
    allocated = {(uid, arm, draw) for uid in all_uids for arm in run.METHODS for draw in run.REPEATS}
    settled = {}
    summaries = []
    for wave, chunk in enumerate(chunks):
        area = run.RUN / f"wave-{wave}"
        if not (area / "RESULTS.json").exists():
            continue
        rows = run.read(area / "RESULTS.json")
        index = {(r["uid"], r["method"], r["replicate"]): r for r in rows}
        if len(rows) != len(index) or set(index) != {k for k in allocated if k[0] in chunk} or set(index) & set(settled):
            raise ValueError("Terminal wave does not match its original allocation")
        summary = run.read(area / "SUMMARY.json")
        if summary["wave"] != wave:
            raise ValueError("Wrong wave summary")
        summaries.append(summary)
        settled.update(index)
    scores = {}
    for key, row in settled.items():
        if (row["status"] == "SCORED") != (row["score"] is not None):
            raise ValueError("Score/availability contradiction")
        if row["score"] is not None:
            scores[key] = metric_values(row["score"], refs[key[0]])
    known = [(uid, draw) for uid in all_uids for draw in run.REPEATS if
             all((uid, arm, draw) in scores for arm in run.METHODS)]
    complete = {uid for uid, n in Counter(uid for uid, _ in known).items() if n == 3}
    pairs = [(scores[uid, run.GATE, draw], scores[uid, run.PAPER, draw], uid) for uid, draw in known]
    unavailable = {(r["unit"]["root_id"], r["unit"]["method"], r["unit"]["replicate"]): r["status"]
                   for r in plan["unavailable"]}
    if set(unavailable) - allocated or any(k in scores for k in unavailable):
        raise ValueError("Original frozen missing Actor units changed")
    states = {arm: Counter(settled[k]["status"] if k in settled else unavailable.get(k, "WAVE_NOT_SETTLED")
                           for k in allocated if k[1] == arm) for arm in run.METHODS}
    full_panel = aggregation(allocated, scores, refs)
    effect_bounds = {}
    for metric in METRICS:
        left = [r["metrics"][metric]["bounds"] for r in full_panel[run.GATE]["draws"]]
        right = [r["metrics"][metric]["bounds"] for r in full_panel[run.PAPER]["draws"]]
        effect_bounds[metric] = ([sum(l[0] - r[1] for l, r in zip(left, right)) / 3,
                                   sum(l[1] - r[0] for l, r in zip(left, right)) / 3]
                                  if all(lo is not None and hi is not None for lo, hi in left + right) else None)
    statuses = Counter()
    for summary in summaries:
        statuses.update(summary["request_statuses"])
    receipt_totals = {"physical_requests": sum(w["new_model_calls"] for w in summaries),
                      "reported_tokens": sum(w["reported_tokens"] for w in summaries),
                      "unknown_usage": sum(w["unknown_usage"] for w in summaries),
                      "request_statuses": statuses}
    return {"plan_sha256": sha(plan), "settled_waves": [s["wave"] for s in summaries],
            "full_allocation_terminal": len(summaries) == len(chunks),
            "allocated_tasks": len(all_uids), "allocated_task_draw_pairs": len(all_uids) * 3,
            "scoring_states": states, "receipts_in_terminal_waves": receipt_totals,
            "bootstrap_seed": SEED, "bootstrap_draws": BOOTSTRAP_DRAWS,
            "allocated_panel": full_panel, "all_allocation_gate_minus_selectivity_bounds": effect_bounds,
            "settled_wave_panel": aggregation(settled, scores, refs) if settled else None,
            "available_pairs": paired_report(pairs, groups),
            "all_three_draw_pairs": paired_report([p for p in pairs if p[2] in complete], groups)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    print(json.dumps(replay(run.read(run.RUN / "PLAN_PRIVATE.json")), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
