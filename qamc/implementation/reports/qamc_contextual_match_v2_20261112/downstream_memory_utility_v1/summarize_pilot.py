"""Aggregate the settled CAR pilot without exporting task, source, or answer text."""
from collections import Counter, defaultdict
from itertools import combinations
import json
import re

from run_car import ARMS, RUN, archive, probe

METHODS = ("BASE", *ARMS)
BOLD = re.compile(r"\bbold\s+text\b", re.I)


def metrics(benchmark, score, stratum=None):
    if score is None:
        return None
    if benchmark == "RPEval":
        match = score.get("match")
        if not match or not match.get("positions"):
            return None
        n, d = match["matched"], match["positions"]
        return {"match": (n, d), "exact": (int(n == d), 1),
                **{f.lower(): (score[f], 1) for f in ("OPB", "UPB", "FM") if score.get(f) is not None}}
    if benchmark == "BenchPreS":
        if any(score.get(f) is None for f in ("aar_numerator", "aar_denominator", "mr_numerator",
                                              "mr_denominator", "task_completeness")):
            return None
        nonbold = [r for r in score["decisions"] if r["appropriate"] and not BOLD.search(r["preference"])]
        reflected = sum(r["label"] == "follow" for r in nonbold)
        return {"aar": (score["aar_numerator"], score["aar_denominator"]),
                "mr": (score["mr_numerator"], score["mr_denominator"]),
                "nonbold_aar": (reflected, len(nonbold)), "completeness": (score["task_completeness"], 1)}
    if score.get("failure_release") is None or score.get("failure_strict_utility") is None:
        return None
    category = score.get("category", stratum)
    if not category or (stratum is not None and category != stratum):
        raise ValueError("PersistBench score does not match its frozen category")
    failure = score["failure_strict_utility"] if category == "beneficial_memory_usage" else score["failure_release"]
    return {"pass": (int(not failure), 1)}


def aggregate(items, methods, primary):
    usable = [x for x in items if all(x["scores"].get(m) is not None for m in methods)]
    totals = {}
    for m in methods:
        f = defaultdict(lambda: [0, 0])
        for row in usable:
            for key, (n, d) in row["scores"][m].items():
                f[key][0] += n
                f[key][1] += d
        totals[m] = dict(f)
    diffs = defaultdict(int)
    bounds = None
    if len(methods) == 2:
        bounds = [0, 0]
        for row in items:
            denominator = row["scores"]["BASE"][primary][1]
            values = [row["scores"].get(m) for m in methods]
            if any(v is not None and v[primary][1] != denominator for v in values):
                raise ValueError("Native denominator differs across methods")
            have = [v[primary][0] if v is not None else None for v in values]
            bounds[0] += (have[1] or 0) - (denominator if have[0] is None else have[0])
            bounds[1] += (denominator if have[1] is None else have[1]) - (have[0] or 0)
        for row in usable:
            left, right = (row["scores"][m][primary] for m in methods)
            if left[1] != right[1]:
                raise ValueError("Primary metric denominator differs between paired answers")
            diffs[row["group"]] += right[0] - left[0]
    return {"allocated": len(items), "common": len(usable), "common_groups": len({r["group"] for r in usable}),
            "totals": totals, "second_minus_first_full_allocation_delta_bounds": bounds,
            "second_minus_first_source_group_signs":
            dict(Counter("positive" if d > 0 else "negative" if d < 0 else "tie" for d in diffs.values()))}


def archived_comparators(panels):
    data = {}
    ids = panels["RPEval"].keys()
    bank = archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json")
    rpe = {r["uid"]: metrics("RPEval", r.get("native_fields")) for r in bank
           if r["uid"] in ids and r["method"] == archive.engine.RP}
    data["RPEval"] = ("RP_REBUILT", rpe)
    for benchmark, method in (("BenchPreS", archive.transfer.bench.METHOD), ("PersistBench", "PB_GEPA")):
        _, _, rows = archive.transfer.context(benchmark)
        data[benchmark] = (method, {r["uid"]: metrics(benchmark, r.get("score"), panels[benchmark][r["uid"]]["stratum"]) for r in rows
                                   if r["uid"] in panels[benchmark] and r["method"] == method})
    return data


def archived_rpe_flags():
    rpe = archive.read(archive.BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]
    return {r["uid"]: r["ipe_c"]["flags"] for r in rpe}


def summarize(results):
    sets = defaultdict(dict)
    protected_baseline_flags = archived_rpe_flags()
    rpe_flags = defaultdict(set)
    executed_copies = set()
    for r in results["rows"]:
        if r["benchmark"] == "RPEval":
            flags = set(r.get("score_flags") or ()) | set(protected_baseline_flags[r["uid"]] or ())
            if flags:
                rpe_flags[r["uid"]].update(flags)
        if r["method"] == "COMMIT" and r.get("outcome") == "COMMITTED":
            executed_copies.add(r["uid"])
        bank = sets[r["benchmark"]]
        row = bank.setdefault(r["uid"], {"group": r["group"], "stratum": r["stratum"], "scores": {
            "BASE": metrics(r["benchmark"], r["base_score"], r["stratum"])}})
        if r["method"] in row["scores"]:
            raise ValueError("Repeated CAR outcome")
        row["scores"][r["method"]] = metrics(r["benchmark"], r["score"], r["stratum"])
    scored = {}
    references = archived_comparators(sets)
    external = {}
    fields = {"RPEval": "match", "BenchPreS": "aar", "PersistBench": "pass"}
    for b, bank in sets.items():
        primary = fields[b]
        items = list(bank.values())
        ref_name, reference = references[b]
        for uid, card in bank.items():
            card["scores"][ref_name] = reference.get(uid)
        external[b] = {m: aggregate(items, (ref_name, m), primary) for m in ARMS}
        strata = {"all": items}
        for stratum in sorted({r["stratum"] for r in items}):
            strata[stratum] = [r for r in items if r["stratum"] == stratum]
        scored[b] = {s: {"all_arms": aggregate(rows, METHODS, primary),
                        "pairwise": {f"{left}/{right}": aggregate(rows, (left, right), primary)
                                     for left, right in combinations(METHODS, 2)}}
                     for s, rows in strata.items()}
    execution = defaultdict(Counter)
    for row in results["rows"]:
        execution[row["benchmark"]][row["method"] + "/" + row.get("outcome", row["actor_status"])] += 1
    sensitivity = {}
    for b, bank in sets.items():
        copies = [r for uid, r in bank.items() if uid in executed_copies]
        sensitivity[b] = {"copy_executed_posthoc": aggregate(copies, METHODS, fields[b])}
        if b == "RPEval":
            sensitivity[b]["any_flag_by_new_arms_or_base"] = len(rpe_flags)
            clear = [r for uid, r in bank.items() if uid not in rpe_flags]
            sensitivity[b]["unflagged_by_all_arms"] = aggregate(clear, METHODS, fields[b])
    return {"scores": scored, "secondary_archive_comparisons": external, "execution": execution,
            "sensitivity": sensitivity, "calls": results["calls"], "statuses": results["statuses"],
            "tokens": results["tokens"], "unknown_usage": results["unknown_usage"],
            "proposal_counts": dict(Counter("no_intervention" if x is None else x["operation"]
                                            for x in results["proposals"].values())),
            "donor_outcomes": dict(Counter(d["origin"] + "/" + d["status"] for d in results["donors"]))}


if __name__ == "__main__":
    settled = probe.read(RUN / "RESULTS.json")
    print(json.dumps(summarize(settled), indent=2, sort_keys=True))
