"""Check author-designated inappropriate nickname text in all paired saved answers."""

from collections import Counter, defaultdict
import json
import re

from freeze_reflection import inventory
from trace_misuse import NICKNAME, run


def audit():
    draws, summary = inventory()
    by_draw = defaultdict(dict)
    for item in draws:
        if item["answer"] is not None:
            by_draw[item["uid"], item["draw"]][item["method"]] = item
    strict, extra = Counter(), Counter()
    for methods in by_draw.values():
        if set(methods) != set(run.METHODS):
            continue
        records = [methods[arm] for arm in run.METHODS]
        counts = strict if all(r["old_strict_score"] for r in records) else extra
        counts["answer_pairs"] += 1
        refs = [[(a["attribute"], a["appropriate"]) for a in r["attributes"]] for r in records]
        if refs[0] != refs[1]:
            raise ValueError("Matched answers have different author reference fields")
        for attribute, appropriate in refs[0]:
            match = NICKNAME.search(attribute)
            if appropriate or match is None:
                continue
            counts["paired_nickname_attributes"] += 1
            pattern = re.compile(r"(?<!\w)" + re.escape(match[1]) + r"(?!\w)")
            for record in records:
                counts[record["method"] + "_literal_present"] += bool(pattern.search(record["answer"]))
    if strict["answer_pairs"] != summary["common_original_strict_score_pairs"]:
        raise ValueError("Original exact-pair counts differ")
    if strict["answer_pairs"] + extra["answer_pairs"] != summary["common_answer_pairs"]:
        raise ValueError("Complete answer-pair count differs")
    return {
        "strict_qwen_pairs": strict, "additional_paired_answers": extra,
        "all_paired_answers": dict(Counter({k: strict[k] + extra[k] for k in strict.keys() | extra.keys()})),
        "new_calls": 0, "original_scores_replaced": 0,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
