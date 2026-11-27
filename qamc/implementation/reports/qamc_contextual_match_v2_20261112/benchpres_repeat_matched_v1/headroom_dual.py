"""Find fixed BenchPreS outcomes supported by both automatic evaluators."""
from collections import Counter, defaultdict
import json

from analyze_reflection import archive_references
from freeze_reflection import PRIVATE, inventory, token
from run_reflection_nonbold_census import ROOT, run, summarize
import run_reflection_gpt41 as sample
from trace_nonbold import BOLD


def audit():
    plan = run.read(ROOT / "PLAN_PRIVATE.json")
    if not (ROOT / "TERMINAL").is_file():
        raise ValueError("Use the terminal masked re-evaluation only")
    draws, _ = inventory()
    archive = {(r["uid"], r["draw"], r["method"]): r for r in draws}
    refs = archive_references()
    seed = bytes.fromhex((PRIVATE / "SEED_PRIVATE").read_text())
    geometry = {token(seed, "census-slot", uid, draw, slot)[:24]: (uid, draw, slot)
                for uid, attrs in refs.items() for draw in run.REPEATS
                for slot, (preference, eligible) in enumerate(attrs)
                if eligible and not BOLD.search(preference)}
    if geometry.keys() != {row["pair"] for row in plan["slots"]}:
        raise ValueError("Source geometry differs from the accepted census")
    labels = {wire: int(value == "yes") for wire, value in plan["cached"].items()}
    for job in plan["units"]:
        receipt, label = sample.receipt(job, ROOT)
        if label in ("yes", "no"):
            if receipt["reference_config_sha256"] != plan["service_sha256"]:
                raise ValueError("Recheck protocol identity")
            labels[receipt["request_sha256"]] = int(label == "yes")

    gate, other = run.GATE, run.PAPER
    tally = {who: Counter() for who in ("Qwen", "GPT4.1")}
    statuses, profiles, tasks = Counter(), defaultdict(set), defaultdict(set)
    successes = set()
    valid_to_replace = Counter()
    condition = {(1, 1): "both_follow", (0, 0): "both_miss",
                 (1, 0): "gate_only", (0, 1): "selectivity_only"}
    for row in plan["slots"]:
        if not row["was_original_common"]:
            continue
        qwen = tuple(row["arms"][m]["original"] for m in (gate, other))
        gpt = tuple(labels.get(row["arms"][m]["request_sha256"]) for m in (gate, other))
        if None in gpt:
            continue
        for name, vals in (("Qwen", qwen), ("GPT4.1", gpt)):
            tally[name].update(dict(zip((gate, other), vals, strict=True)))
        key = condition[qwen] if qwen == gpt else "judge_disagree"
        uid, draw, _ = geometry[row["pair"]]
        statuses[key] += 1
        tasks[key].add(uid)
        profiles[key].add(archive[uid, draw, gate]["profile_group"])
        if key == "selectivity_only":
            successes.add((uid, draw))
    primary = summarize(plan)["paired_both_evaluators"]
    if sum(statuses.values()) != primary["positions"] or any(tally[k] != primary[k] for k in tally):
        raise ValueError("Primary evaluator totals differ")
    for uid, draw in successes:
        strong, comparison = (archive[uid, draw, arm] for arm in (gate, other))
        mandatory = []
        for a, b in zip(strong["attributes"], comparison["attributes"], strict=True):
            if (a["attribute"], a["appropriate"]) != (b["attribute"], b["appropriate"]):
                raise ValueError("Attribute binding differs")
            if a["appropriate"] and BOLD.search(a["attribute"]):
                mandatory.append((a["follow"], b["follow"]))
        def misuse(r):
            return sum(a["follow"] for a in r["attributes"] if not a["appropriate"])
        valid_to_replace.update({
            "available_whole_answer_pairs": 1,
            "no_qwen_completeness_loss": int(comparison["old_completeness"] >= strong["old_completeness"]),
            "no_qwen_mr_increase": int(misuse(comparison) <= misuse(strong)),
            "no_qwen_bold_regression": int(all(b >= a for a, b in mandatory)),
            "qwen_bold_positions": len(mandatory),
        })
    return {"common_positions": primary["positions"], "qwen_and_gpt41": statuses,
            "distinct_profiles_by_outcome": {k: len(v) for k, v in sorted(profiles.items())},
            "distinct_tasks_by_outcome": {k: len(v) for k, v in sorted(tasks.items())},
            "selectivity_only_whole_answer_guards": valid_to_replace,
            "same_answer_automatic_judges": 2, "independent_human_votes": 0, "physical_requests_added": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
