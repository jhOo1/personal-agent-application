"""Compare evaluators on identical frozen non-bold pairs, grouped by profile."""

from collections import Counter, defaultdict
import json
from random import Random

from freeze_reflection import PRIVATE, token
from report_qamc_benchpres_three_draw import BOOTSTRAP_DRAWS, SEED
from run_reflection_nonbold_census import ROOT, summarize, run
import run_reflection_gpt41 as sample
from analyze_reflection import archive_references
from trace_nonbold import BOLD


def profile_effect(rows):
    by_profile = defaultdict(Counter)
    for g in rows:
        cell = by_profile[g["profile"]]
        cell["slots"] += 1
        for evaluator in ("Qwen", "GPT4.1"):
            cell[evaluator] += g[evaluator][run.GATE] - g[evaluator][run.PAPER]
    values = [by_profile[k] for k in sorted(by_profile)]
    output = {"positions": len(rows), "tasks": len({g["uid"] for g in rows}), "profiles": len(values)}
    for evaluator in ("Qwen", "GPT4.1", "difference_of_effects"):
        def effect(cell):
            if evaluator == "difference_of_effects":
                return cell["GPT4.1"] - cell["Qwen"]
            return cell[evaluator]
        relative = [effect(x) / x["slots"] for x in values]
        signs = Counter("positive" if d > 0 else "negative" if d < 0 else "tie" for d in relative)
        numerator = sum(effect(x) for x in values)
        if len(values) >= 2:
            rng = Random(SEED)
            scores = []
            for _ in range(BOOTSTRAP_DRAWS):
                sampled = [values[rng.randrange(len(values))] for _ in values]
                scores.append(sum(effect(x) for x in sampled) / sum(x["slots"] for x in sampled))
            scores.sort()
            interval = [scores[int((len(scores) - 1) * q)] for q in (0.025, 0.975)]
        else:
            interval = None
        output[evaluator] = {
            "gate_minus_selectivity_net_positions": numerator,
            "micro_delta": numerator / len(rows) if rows else None,
            "profile_macro_delta": sum(relative) / len(relative) if relative else None,
            "profile_direction_counts": signs,
            "profile_bootstrap_interval": interval,
        }
    return output


def run_analysis(plan):
    if not (ROOT / "TERMINAL").exists():
        raise ValueError("Only settled phases enter this source-group comparison")
    source = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(source)
    profiles = {r["uid"]: r["analysis_group_id"] for r in source["cases"]}
    reviewed = {row["id"]: row for row in run.read(sample.SOURCE / "PLAN_PRIVATE.json")["jobs"]}
    private_roles = run.read(PRIVATE / "CUSTODIAN_ONLY.json")["rater_ids"]["A"]
    previous_roots = {private_roles[key][0] for key in reviewed}
    seed = bytes.fromhex((PRIVATE / "SEED_PRIVATE").read_text())
    refs = archive_references()
    geometry = {
        token(seed, "census-slot", uid, draw, pos)[:24]: (uid, draw)
        for uid, attrs in refs.items() for draw in run.REPEATS
        for pos, (text, allowed) in enumerate(attrs) if allowed and not BOLD.search(text)
    }
    if geometry.keys() != {slot["pair"] for slot in plan["slots"]}:
        raise ValueError("Reconstructed slot geometry differs from the fixed census")
    labels = dict(plan["cached"])
    for job in plan["units"]:
        row, label = sample.receipt(job, ROOT)
        if row and row["reference_config_sha256"] != plan["service_sha256"]:
            raise ValueError("Wrong scoring service")
        if label in ("yes", "no"):
            labels[row["request_sha256"]] = label
    rows = []
    for slot in plan["slots"]:
        if not slot["was_original_common"]:
            continue
        latest = {method: {"yes": 1, "no": 0}.get(labels.get(arm["request_sha256"]))
                  for method, arm in slot["arms"].items()}
        if any(v is None for v in latest.values()):
            continue
        old = {m: v["original"] for m, v in slot["arms"].items()}
        if any(d not in (0, 1) for d in old.values()):
            raise ValueError("Original strict Judge label missing")
        uid, draw = geometry[slot["pair"]]
        rows.append({"uid": uid, "draw": draw, "profile": profiles[uid], "Qwen": old, "GPT4.1": latest})
    primary = summarize(plan)["paired_both_evaluators"]
    if len(rows) != primary["positions"]:
        raise ValueError("Common-evaluator pair count differs from census")
    for judge in ("Qwen", "GPT4.1"):
        if primary[judge] != {m: sum(x[judge][m] for x in rows) for m in run.METHODS}:
            raise ValueError("Common-evaluator totals differ from census")
    return {
        "all_common": profile_effect(rows),
        "exclude_earlier_diagnostic_tasks": profile_effect([r for r in rows if r["uid"] not in previous_roots]),
        "independent_human_votes": 0, "model_calls_added": 0,
    }


if __name__ == "__main__":
    print(json.dumps(run_analysis(run.read(ROOT / "PLAN_PRIVATE.json")), indent=2, sort_keys=True))
