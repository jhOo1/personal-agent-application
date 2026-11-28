"""Reattach a local execution-side review to exact saved BU receipts."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE.parents[2] / "runs" / HERE.parent.name
PACKET = RUNS / "blind_utility_behavior_v1" / "private"


def load(path):
    return json.loads(path.read_text())


def main():
    criteria, judgments, answers, key, exposures = (load(PACKET / name) for name in (
        "OPERATOR_CRITERIA_V1.json", "OPERATOR_JUDGMENTS_V1.json", "02_ANONYMOUS_ANSWERS.json",
        "UNBLIND_KEY.json", "UNBLIND_SOURCES.json"))
    original = load(RUNS / HERE.name / "private/SETTLED.json")
    grades = {(r["uid"], r["arm"]): r for r in original["rows"]}
    summaries = Counter()
    patterns = Counter()
    if criteria.keys() != judgments.keys() or len(criteria) != 6:
        raise ValueError("Targeted review scope changed")
    for packet, statuses in judgments.items():
        if len(statuses) != 2 or statuses.keys() != answers[packet].keys():
            raise ValueError("Operator judgment does not cover the exact two answers")
        entry = key[packet]
        expected = set(criteria[packet]["source_ids"])
        seen = {}
        for row in entry["positions"]:
            arm, answer_id = row["arm"], row["answer_id"]
            answer = answers[packet][answer_id]
            if sha256(answer.encode()).hexdigest() != row["answer_sha256"]:
                raise ValueError("Review answer identity changed")
            score = grades[entry["uid"], arm]
            state = statuses[answer_id]
            count = len(expected & set(exposures[packet][arm]))
            summaries[arm + "/" + state] += 1
            summaries[arm + "/all_target_sources_delivered"] += count == len(expected)
            if state != "MET":
                summaries[arm + "/not_met_with_all_sources_delivered"] += count == len(expected)
                summaries[arm + "/not_met_with_adapted_GPT_pass"] += score["GPT"] == 3
                summaries[arm + "/not_met_with_adapted_Qwen_pass"] += score["Qwen"] == 3
            seen[arm] = state
        patterns[seen["FULL"] + "/" + seen["SELECTED"]] += 1
    print(json.dumps({"source_groups": len(criteria), "states": summaries, "paired_full_then_selected": patterns,
                      "new_model_calls": 0, "independent_reviewers": 0}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
