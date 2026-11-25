"""Check native RPEval judging against truly history-free archived generation."""
from collections import Counter, defaultdict
import json

import analyze_fixed_answer_choice_v44 as audit
from qamc_rpeval_terminal_judge_sensitivity import inspect

run, task = audit.run, audit.task


def analyze():
    prior = run.read(run.stage.prior.OUT / "FROZEN.json")
    drafts = task.saved_drafts(prior)
    frozen = run.read(task.OUT / "FROZEN.json")
    scored, physical = task.collect(frozen)
    terminal = run.read(task.OUT / "RESULTS.json")
    if terminal["ledger"] != physical:
        raise ValueError("Task-only native responses changed")
    rows = {r["uid"]: r for r in scored}
    endpoints = {r["uid"]: r["task_only"] for r in terminal["roots"]}
    contexts, groups, counts = set(), set(), Counter()
    base_systems, fixed_query = set(), defaultdict(list)
    for root in prior["roots"]:
        uid = root["uid"]
        row = rows[uid]
        cell = row["native"][audit.ZERO]
        if cell != endpoints[uid]:
            raise ValueError("Task-only result did not match its scored receipt")
        if set(row["labels"]) != {"A"} or "match" not in cell["fields"]:
            continue
        wire = run.stage.prior.task_only_request(root)
        wire_hash = run.sha(wire)
        payload = json.loads(wire["messages"][1]["content"])
        if (wire_hash != root["task_wire_sha256"] or payload["source_evidence"] or
                payload["preference_use_policy"]):
            raise ValueError("Task-only negative control received long-term history")
        answer = drafts[wire_hash]["answer"]
        grade_wire = frozen["ready"][uid]["graded_wire_sha256"]
        if run.sha(answer) != frozen["ready"][uid]["answer_sha256"]:
            raise ValueError("Archived score uses another answer")
        entry = inspect({"uid": uid, "method": audit.ZERO, "answer": answer,
                         "native_fields": cell["fields"], "raw_scores": {run.stage.JUDGE: cell["raw"]}}, row["labels"])
        scores = cell["fields"]
        contexts.add(bool(payload["current_context"] or payload["facts"]))
        groups.add(root["group"])
        base_systems.add(run.sha(wire["messages"][0]))
        counts.update(roots=1, positions=entry["positions"], matched=entry["matched"],
                      less_than_full=entry["matched"] < entry["positions"], all_zero=entry["matched"] == 0,
                      native_OPB_positive=scores.get("OPB", 0) > 0, missing_OPB="OPB" not in scores,
                      rule_flagged=bool(entry["flags"]), **dict(Counter(entry["flags"])))
        fixed_query[(wire_hash, row["labels"], run.sha(answer))].append({
            "uid": uid, "source_group": root["group"], "grade_wire_sha256": grade_wire,
            "score": scores, "raw_judge": cell["raw"], "rule_flags": entry["flags"],
        })
    matched = [group for group in fixed_query.values() if len(group) > 1]
    disagreements = [{"actor_wire_sha256": k[0], "author_labels": k[1], "answer_sha256": k[2], "rows": values}
                     for k, values in fixed_query.items() if len({x["score"]["match"]["matched"] for x in values}) > 1]
    return {
        "new_model_calls": 0, "source_groups": len(groups), "distinct_system_prompts": len(base_systems),
        "nonempty_public_context_presence": sorted(contexts), "all_A": counts,
        "identical_generation_and_gold_label_repeated_groups": len(matched),
        "identical_generation_and_gold_label_conflicting_match": disagreements,
        "scope": "Exposed held-by-project drafts. Raw native scores remain unchanged. "
                 "Generated recommendations can overlap hidden preferences, but overlap does not identify memory access.",
    }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
