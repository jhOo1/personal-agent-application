"""Verify transfer receipts and compute paired, source-grouped native comparisons."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
import random
import re

from qamc.common import sha

import run_realization_transfer as run


def paired_summary(rows):
    """Each row carries a common source group, two numerators and a common denominator."""
    buckets = defaultdict(lambda: [0, 0, 0])
    for group, left, right, denominator in rows:
        row = buckets[group]
        row[0] += left
        row[1] += right
        row[2] += denominator
    grouped = list(buckets.values())
    left, right, total = map(sum, zip(*grouped)) if grouped else (0, 0, 0)
    output = {"roots": len(rows), "groups": len(grouped), "left": left, "right": right,
              "denominator": total, "delta": (right - left) / total if total else None, "source_ci95": None}
    if len(grouped) < 2 or not total:
        return output
    rng = random.Random(1937)
    values = []
    for _ in range(4000):
        sampled = rng.choices(grouped, k=len(grouped))
        a, b, n = map(sum, zip(*sampled))
        if n:
            values.append((b - a) / n)
    values.sort()
    if values:
        output["source_ci95"] = [values[int(fraction * (len(values) - 1))] for fraction in (.025, .975)]
    return output


def nonbold(row):
    relevant = [d for d in row["decisions"] if d["appropriate"]
                and not re.search(r"\bbold\s+text\b", d["preference"], re.I)]
    return sum(d["label"] == "follow" for d in relevant), len(relevant)


def bench_comparison(pairs):
    metrics = defaultdict(list)
    for case, a, b in pairs:
        group = case["analysis_group_id"]
        for key in ("aar", "mr"):
            n = a[f"{key}_denominator"]
            if n != b[f"{key}_denominator"]:
                raise ValueError("Different frozen BenchPreS attribute denominators")
            metrics[key].append((group, a[f"{key}_numerator"], b[f"{key}_numerator"], n))
        x, nx = nonbold(a)
        y, ny = nonbold(b)
        if nx != ny:
            raise ValueError("Different frozen BenchPreS non-bold denominators")
        metrics["nonbold_aar"].append((group, x, y, nx))
        metrics["completeness"].append((group, a["task_completeness"], b["task_completeness"], 1))
    return {key: paired_summary(rows) for key, rows in metrics.items()}


def persist_comparison(pairs):
    by_category = defaultdict(list)
    for case, a, b in pairs:
        by_category[case["category"]].append((case["group_id"], a, b))
    return {category: {key: paired_summary([(group, a[key], b[key], 1) for group, a, b in rows])
                       for key in ("failure_release", "failure_strict_utility")}
            for category, rows in by_category.items()}


def persist_activation(cases, logical, scores, selection):
    dispositions, common = defaultdict(Counter), defaultdict(list)
    for uid, case in cases.items():
        direct, full, main = (logical[uid, arm] for arm in run.ARMS)
        count = dispositions[case["category"]]
        count["assigned"] += 1
        if selection[uid]["status"] != "OK":
            count["selector_unusable"] += 1
            continue
        uses = selection[uid].get("uses", ())
        count["without_admitted_memory"] += not uses
        count["with_optional_license"] += any(edge["use"] == "OPTIONAL" for edge in uses)
        if main["actor_status"] != "OK":
            count["main_actor_unusable"] += 1
            continue
        count["valid_main"] += (uid, run.MAIN_ONLY) in scores
        split_wire = direct["actor_sha256"] != main["actor_sha256"]
        appended = full.get("answer") != main.get("answer")
        count["changed_rendering_request"] += split_wire
        count["appended_answer"] += appended
        for other, label in ((run.method.DIRECT, "changed_rendering"), (run.method.SEGMENTED, "appended_answer")):
            if (uid, other) not in scores or (uid, run.MAIN_ONLY) not in scores:
                continue
            if (other == run.method.DIRECT and split_wire) or (other == run.method.SEGMENTED and appended):
                common[label].append((case, scores[uid, other], scores[uid, run.MAIN_ONLY]))
    return {"dispositions": dispositions,
            "within_activated_treatment": {label: persist_comparison(rows) for label, rows in common.items()}}


def shared_persist_controls(cases, scores):
    methods = (run.MAIN_ONLY, "GEPA_SELECTED_BOUNDS", "RPR_PAPER_FULL", "PB_RUBRIC", "PB_GEPA", "PB_NO_MEMORY")
    by_category = defaultdict(list)
    for uid, case in cases.items():
        if all((uid, arm) in scores for arm in methods):
            by_category[case["category"]].append((uid, case))
    return {category: {
        "roots": len(members), "groups": len({case["group_id"] for _, case in members}),
        **{key: {arm: sum(scores[uid, arm][key] for uid, _ in members) for arm in methods}
           for key in ("failure_release", "failure_strict_utility")},
    } for category, members in by_category.items()}


def verify_actor_allocation(benchmark):
    """Rebuild the physical Actor wires from the exposed inputs and recorded Selector replies."""
    folder = run.OUT / benchmark
    plan = run.read(run.OUT / "FROZEN.json")["panels"][benchmark]
    roots = run.development_roots(benchmark)
    selectors = {root["uid"]: run.method.selector(root) for root in roots}
    expected_roots = {root["uid"]: sha([root["public_task"], root["original_sources"], selectors[root["uid"]]])
                      for root in roots}
    if expected_roots != plan["roots"]:
        raise ValueError("Frozen public roster or Selector request changed")
    run.probe.OUT, run.probe.RUN = folder, run.RUN / benchmark
    recorded = run.probe.stage_receipts(run.parent.PLAN)
    if any(record is None or record["status"] == "PENDING_DELIVERY_UNKNOWN" for record, _ in recorded.values()):
        raise ValueError("Actor dispatch exists before all Selector attempts settled")
    by_hash = {record["request_sha256"]: (record, raw) for record, raw in recorded.values()}
    hashes = {uid: sha(wire) for uid, wire in selectors.items()}
    if set(hashes.values()) != by_hash.keys() or len(by_hash) != len(recorded):
        raise ValueError("Selector receipts differ from the frozen set of request digests")
    selected = {(uid, "SHARED_USES"): by_hash[digest] for uid, digest in hashes.items()}
    traces, jobs = run.parent.actor_jobs(roots, selected, {"selector_wires": hashes})
    pairs = defaultdict(dict)
    for uid, arm, wire in jobs:
        pairs[uid][arm] = wire
    for uid, pair in pairs.items():
        direct, compiled = (pair[arm] for arm in run.method.METHODS)
        if direct != compiled:
            if traces[uid]["route"] != "SEGMENTED":
                raise ValueError("Unexpected difference in a shared Actor request")
            normalized = {**compiled, "messages": [direct["messages"][0], *compiled["messages"][1:]]}
            if direct != normalized:
                raise ValueError("Split Actor requests differ outside rendering instructions")
        elif traces[uid]["route"] == "SEGMENTED":
            raise ValueError("Segmented route did not change the Actor request")
    manifest = run.read(folder / "Actor_MANIFEST.json")["units"]
    expected = {}
    for uid, arm, wire in jobs:
        expected.setdefault(sha(wire), (uid, arm))
    actual = {sha(entry["request"]): (entry["unit"]["root_id"], entry["unit"]["method"]) for entry in manifest}
    if actual != expected or len(actual) != len(manifest):
        raise ValueError("Actor manifest differs from the same-evidence reconstruction")
    return traces, len(actual)


def settle(benchmark):
    folder = run.OUT / benchmark
    state = run.read(folder / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError(f"{benchmark} has not settled")
    frozen = run.read(run.OUT / "FROZEN.json")["panels"][benchmark]
    saved = run.read(folder / "SETTLED.json")
    ledger = {(row["unit"]["stage"], row["request_sha256"]): row for row in saved["ledger"]}
    if not len(ledger) == len(saved["ledger"]) == saved["physical_requests"] == state["physical_requests"]:
        raise ValueError("Duplicate or missing physical receipts")
    actual = {}
    run.probe.OUT, run.probe.RUN = folder, run.RUN / benchmark
    for stage, maximum in frozen["caps"].items():
        receipts = run.probe.stage_receipts(stage)
        if len(receipts) > maximum:
            raise ValueError("Physical request cap exceeded")
        for record, answer in receipts.values():
            if (record is None or record["status"] == "PENDING_DELIVERY_UNKNOWN"
                    or (record["status"] == "OK") != bool(answer)):
                raise ValueError("Terminal receipt is absent or unconfirmed")
            key = (stage, record["request_sha256"])
            if key in actual:
                raise ValueError("A stage has dispatched the same request more than once")
            actual[key] = record
    if actual != ledger:
        raise ValueError("Terminal ledger differs from durable request records")
    checked_selector, verified_actors = verify_actor_allocation(benchmark)
    if checked_selector != saved["selector"] or sum(stage == run.parent.ACTOR for stage, _ in actual) != verified_actors:
        raise ValueError("Actor allocation or saved Selector trace differs from receipts")
    cases, protocol, controls = run.context(benchmark)
    expected = {(uid, arm) for uid in cases for arm in run.ARMS}
    logical = {(r["uid"], r["method"]): r for r in saved["rows"]}
    if (logical.keys() != expected or len(logical) != len(saved["rows"])
            or cases.keys() != frozen["roots"].keys()):
        raise ValueError("Settled score matrix differs from the frozen roster")
    for uid in cases:
        main, full = (logical[uid, arm] for arm in (run.MAIN_ONLY, run.method.SEGMENTED))
        if (main["actor_sha256"] != full["actor_sha256"] or
                (main.get("answer") != full.get("answer")
                 and not (main.get("answer") and full.get("appended_sources")
                          and full["answer"].startswith(main["answer"] + "\n\n")))):
            raise ValueError("Treatment changed the same-draft main answer")
    scores = {(r["uid"], r["method"]): r["score"] for r in (*saved["rows"], *controls) if r["score"] is not None}
    compare = bench_comparison if benchmark == "BenchPreS" else persist_comparison
    comparisons = {}
    for arm in (run.method.DIRECT, run.method.SEGMENTED, *sorted({r["method"] for r in controls})):
        pairs = [(cases[uid], scores[uid, arm], scores[uid, run.MAIN_ONLY]) for uid in cases
                 if (uid, arm) in scores and (uid, run.MAIN_ONLY) in scores]
        comparisons[arm] = compare(pairs)
    sizes = Counter(stage for stage, _ in actual)
    actor_model = run.read(folder / "Actor_MANIFEST.json")["protocol"]["model"]
    generation = [rec.get("usage") or {} for (stage, _), rec in actual.items()
                  if stage in {run.parent.PLAN, run.parent.ACTOR}]
    selection = saved["selector"]
    selector_status = Counter(row["status"] for row in selection.values())
    selector_routes = Counter(row["route"] for row in selection.values() if "route" in row)
    admitted_uses = Counter(edge["use"] for row in selection.values() for edge in row.get("uses", ()))
    shared = sum(logical[uid, run.method.DIRECT]["actor_sha256"] is not None
                 and logical[uid, run.method.DIRECT]["actor_sha256"] == logical[uid, run.MAIN_ONLY]["actor_sha256"]
                 for uid in cases)
    reason_keys = ("actor_status", "score_error")
    missing = Counter(tuple(str(r.get(key, "NONE")) for key in reason_keys)
                      for r in saved["rows"] if r["method"] == run.MAIN_ONLY and r["score"] is None)
    diagnostics = {}
    if benchmark == "PersistBench":
        diagnostics = {"activation": persist_activation(cases, logical, scores, selection),
                       "common_strong_controls": shared_persist_controls(cases, scores)}
    return {"benchmark": benchmark, "assigned": saved["assigned"], "actor_model": actor_model,
            "judge_model": protocol["model"], "valid_scores": saved["valid_scores"], "pairwise": comparisons,
            "appended_cases": saved["appended_cases"], "requests_by_stage": sizes,
            "selector_status": selector_status, "selector_routes": selector_routes, "admitted_uses": admitted_uses,
            "shared_direct_main_actor_request_roots": shared,
            "main_missing_scores": [{"actor_status": status, "score_error": error, "roots": count}
                                    for (status, error), count in sorted(missing.items())],
            "physical_requests": saved["physical_requests"], "transport": saved["transport"],
            "known_tokens": saved["known_tokens"], "unknown_usage": saved["unknown_usage"],
            "generation_known_tokens": sum(x.get("total_tokens", 0) for x in generation),
            "generation_unknown_tokens": sum("total_tokens" not in x for x in generation),
            "cache": saved["cache"], "settled_file_sha256": sha((folder / "SETTLED.json").read_bytes()),
            "source_groups": len({c.get("analysis_group_id", c["group_id"]) for c in cases.values()}),
            "independent_confirmation": False, **diagnostics}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", choices=run.PANELS)
    summary = settle(parser.parse_args().benchmark)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
