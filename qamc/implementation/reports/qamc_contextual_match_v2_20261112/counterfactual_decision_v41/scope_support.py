"""Audit which query/memory contrasts are naturally identifiable in the existing panels."""
from collections import Counter, defaultdict
import json

from qamc.common import sha
from qamc.pa.core import digest
from run_v41 import OUT, author_cases, formal, read
from transfer_replay import bench, development, persist


def source_reuse(rows):
    task_sets, source_sets, labels = defaultdict(set), defaultdict(set), defaultdict(set)
    for row in rows:
        task, texts = row["task"], row["texts"]
        task_sets[sha(texts)].add(task)
        for text in texts:
            source_sets[sha(text)].add(task)
        for text, label in row.get("author_source_labels", ()):
            labels[sha(text)].add(label)
    repeated = {key for key, tasks in source_sets.items() if len(tasks) > 1}
    return {
        "roots": len(rows), "distinct_task_conditions": len({r["task"] for r in rows}),
        "distinct_ordered_text_lists": len(task_sets),
        "whole_history_reused_across_task_conditions": sum(len(tasks) > 1 for tasks in task_sets.values()),
        "distinct_memory_literals": len(source_sets), "literals_reused_across_task_conditions": len(repeated),
        "cross_task_repeated_literals_with_multiple_author_labels": (
            sum(len(labels[key]) > 1 for key in repeated) if labels else None
        ),
    }


def rpeval_data():
    frozen = read(OUT / "FROZEN.json")
    exposed = author_cases(read(formal.OUT / "PLAN.json"))
    rows = []
    for root in frozen["roots"]:
        case = exposed[root["uid"]]
        evaluation = read(formal.ROOT / case["evaluation_path"])
        if digest(evaluation) != case["evaluation_hash"]:
            raise ValueError("RPEval author reference changed")
        texts = [m["text"] for m in root["original_sources"]]
        rows.append({"task": root["task_wire_sha256"], "texts": texts,
                     "author_source_labels": list(zip(texts, evaluation["intent_type"], strict=True))})
    return rows


def bench_data():
    plan = read(bench.OUT / "PLAN.json")
    cases = [c for c in plan["cases"] if c["independent_confirmation"] is False]
    if len(cases) != 48:
        raise ValueError("BenchPreS development subset not preserved")
    groups, rows = defaultdict(list), []
    for case in cases:
        task = development.task_for(case)
        task_sha = sha([task.query, task.current_context, task.fixed_facts])
        texts = [m.text for m in task.memories]
        profile = sha(texts)
        ref = read(development.ROOT / case["evaluation_path"])
        if digest(ref) != case["evaluation_hash"]:
            raise ValueError("BenchPreS author reference changed")
        labels = {}
        for attr, applicable in zip(ref["preference_attribute"], ref["preference_label"], strict=True):
            if texts.count(attr) != 1 or type(applicable) is not bool:
                raise ValueError("Raw preference does not uniquely match public profile")
            labels[attr] = applicable
            groups[profile, sha(attr)].append({"uid": case["uid"], "task": task_sha, "label": applicable})
        rows.append({"task": task_sha, "texts": texts, "author_source_labels": list(labels.items())})
    repeats = [values for values in groups.values() if len({row["task"] for row in values}) > 1]
    pattern = Counter(
        "flips" if len({row["label"] for row in values}) > 1
        else "always_applicable" if values[0]["label"] else "always_inapplicable"
        for values in repeats
    )
    baseline = Counter()
    for cases_with_attr in repeats:
        for row in cases_with_attr:
            peers = [c["label"] for c in cases_with_attr if c["task"] != row["task"]]
            if peers and peers.count(True) != peers.count(False):
                baseline.update(position_covered=1, agreement=(peers.count(True) > peers.count(False)) == row["label"])
    return {**source_reuse(rows), "profile_attribute_pairs": len(groups),
            "repeated_profile_attributes_by_author_label_pattern": {
                key: pattern[key] for key in ("always_applicable", "always_inapplicable", "flips")
            }, "leave_one_task_label_only": baseline}


def persist_data():
    bank = {c["uid"]: c for c in read(development.OUT / "PLAN.json")["cases"] if c["benchmark"] == "persistbench"}
    cases = [c for c in read(persist.AUTHOR_OUT / "PLAN.json")["cases"] if c["role"] == "DEV"]
    if len(cases) != 60:
        raise ValueError("PersistBench development subset not preserved")
    rows = []
    for case in cases:
        task = development.task_for(bank[case["uid"]])
        rows.append({"task": sha([task.query, task.current_context, task.fixed_facts]),
                     "texts": [m.text for m in task.memories]})
    return {**source_reuse(rows), "categories": Counter(c["category"] for c in cases)}


if __name__ == "__main__":
    print(json.dumps({"rpeval": source_reuse(rpeval_data()), "benchpres": bench_data(),
                      "persistbench": persist_data(), "new_model_requests": 0,
                      "diagnostic_only": True, "sealed_cases": 0}, ensure_ascii=False, indent=2))
