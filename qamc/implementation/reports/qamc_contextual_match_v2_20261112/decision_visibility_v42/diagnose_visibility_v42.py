"""Separate the observed Selector decisions from what aggregate native scores identify."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from qamc.common import sha
from qamc.pa.core import digest
from qamc_rpeval_terminal_judge_sensitivity import inspect, pair_bounds

from audit_visibility_v42 import replay_stage
from label_bounds import add_pair, cell_bounds
import run_visibility_v42 as runner


def panels():
    freeze = runner.read(runner.OUT / "FROZEN.json")
    if freeze != runner.prepare():
        raise ValueError("The live experiment or its inputs differ from the freeze")
    old = runner.read(runner.prior.OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in old["roots"]}
    exposed = runner.prior.author_cases(runner.read(runner.prior.formal.OUT / "PLAN.json"))
    return freeze, roots, exposed


def selector_wave(index):
    plan, roots, refs = panels()
    if not 0 <= index < len(plan["waves"]):
        raise ValueError("Unknown frozen wave")
    selected_cache, counts = {runner.SELECTOR: {}}, Counter()
    for i, uids in enumerate(plan["waves"][:index + 1]):
        wave = f"wave_{i:02d}"
        runner.PROBE.OUT, runner.PROBE.RUN = runner.OUT / wave, runner.RUN / wave
        jobs = [(uid, method, runner.selection_request(roots[uid], method))
                for uid in uids for method in runner.METHOD_PROMPTS]
        replay_stage(wave, runner.SELECTOR, jobs, selected_cache, counts)
    labels = {}
    for uid in uids:
        ref = refs[uid]
        raw = runner.read(runner.prior.formal.ROOT / ref["evaluation_path"])
        if digest(raw) != ref["evaluation_hash"]:
            raise ValueError("Author label reference changed")
        labels[uid] = raw["intent_type"]
    results = defaultdict(Counter)
    for uid, method, wire in jobs:
        record, raw = selected_cache[runner.SELECTOR][sha(wire)]
        stats = results[method]
        stats["assigned"] += 1
        if raw is None:
            stats[runner.status(record)] += 1
            continue
        try:
            scope = runner.compile_scope(roots[uid], raw)
        except (ValueError, KeyError, TypeError):
            stats["invalid_contract"] += 1
            continue
        levels = dict.fromkeys((row["memory_id"] for row in roots[uid]["original_sources"]), "A")
        for use in scope:
            mid = use["memory_id"]
            levels[mid] = max(levels[mid], use["level"])
        aligned = list(zip(labels[uid], levels.values(), strict=True))
        stats["valid_scope"] += 1
        stats.update(f"{a}_as_{b}" for a, b in aligned)
        tag = "all_A" if set(labels[uid]) == {"A"} else "contains_BC"
        stats[tag + "_roots"] += 1
        stats[tag + "_empty"] += not scope
    return {"wave": wave, "roots": len(uids), "source_groups": len({roots[uid]["group"] for uid in uids}),
            "selector_comparison": results, "actor_or_native_outcomes_measured": 0,
            "new_model_calls": 0}


def settled_judges():
    plan, roots, _ = panels()
    summaries = defaultdict(lambda: defaultdict(Counter))
    flags, settled = defaultdict(Counter), 0
    for index, uids in enumerate(plan["waves"]):
        folder = runner.OUT / f"wave_{index:02d}"
        path = folder / "COMPLETED.json"
        if not path.exists():
            break
        rows = runner.read(path)["rows"]
        if [row["uid"] for row in rows] != uids:
            raise ValueError("Settled set changed")
        settled += len(rows)
        for row in rows:
            uid, labels = row["uid"], row["labels"]
            bounds, inspected = {}, {}
            answers = {name: value["answer"] for name, value in {**roots[uid]["archived"], **row["answers"]}.items()}
            for method, result in row["native"].items():
                fields, raw = result["fields"], result["raw"]
                limits = cell_bounds(labels, fields)
                if limits is None:
                    flags[method]["missing_match"] += 1
                    continue
                bounds[method] = limits
                inspected[method] = inspect({"uid": uid, "method": method, "native_fields": fields,
                                             "answer": answers[method], "raw_scores": {runner.JUDGE: raw}}, labels)
                flags[method]["valid_match"] += 1
                flags[method].update(inspected[method]["flags"])
            for left, right in runner.COMPARISONS:
                if not {left, right} <= bounds.keys():
                    continue
                a, b = inspected[left], inspected[right]
                same = a["answer_sha256"] == b["answer_sha256"] and a["judge_sha256"] == b["judge_sha256"]
                lo, hi = pair_bounds(b, a)
                for group in ("all", "all_A" if set(labels) == {"A"} else "contains_BC"):
                    pair = f"{left}__{right}/{group}"
                    summaries[pair]["dispute"].update(roots=1, positions=len(labels),
                                                       flagged_roots=bool(a["flags"] or b["flags"]),
                                                       delta_low=lo, delta_high=hi)
                    for lens in ("match_only", "bias_conditioned"):
                        if bounds[left][lens] is not None and bounds[right][lens] is not None:
                            add_pair(summaries[pair][lens], bounds[left][lens], bounds[right][lens], labels, same)
    return {
        "settled": settled, "planned": len(roots), "native_score_changes": 0, "new_model_calls": 0,
        "flags": flags, "comparisons": summaries,
        "interpretation": "Feasible Judge error counts. These do not locate behaviors or replace native scores.",
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--selector-wave", type=int)
    args = parser.parse_args()
    result = settled_judges() if args.selector_wave is None else selector_wave(args.selector_wave)
    print(json.dumps(result, ensure_ascii=False, indent=2))
