"""Verify that response generation used only the correct anchored tests."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
experiment = run_path(str(HERE / "trial.py"))


def check():
    cards, packets, jobs, pin = experiment["prepare"]()
    read, sha = experiment["read"], experiment["sha"]
    assert read(experiment["PRIVATE"] / "FREEZE.json") == pin
    settled = read(experiment["PRIVATE"] / "SETTLED.json")
    plans = {(uid, arm): plan for uid, arm, plan in settled["plans"]}
    stages = {"ExecutionReview": {}, "ExecutionActor": {}}
    for path in experiment["RUN"].glob("*/visible/*/record.json"):
        record = read(path)
        unit = record["unit"]
        if unit["stage"] not in stages:
            continue
        key = unit["root_id"], unit["method"]
        wire = read(path.with_name("request.json"))
        assert record["request_sha256"] == sha(wire)
        assert key not in stages[unit["stage"]]
        stages[unit["stage"]][key] = wire
    assert jobs == stages["ExecutionReview"]
    assert plans.keys() == stages["ExecutionActor"].keys()
    for (uid, arm), plan in plans.items():
        packet = packets[uid]
        assert experiment["parse_plan"](json.dumps(plan), packet) == plan
        expected = experiment["body"](
            experiment["ACTOR"], packet | {"acceptance_tests": plan["tests"]}
        )
        assert stages["ExecutionActor"][uid, arm] == expected
    counts, repeat_source = {}, {}
    for arm in experiment["ARMS"]:
        subset = [plan["tests"] for (_, method), plan in plans.items() if method == arm]
        counts[arm] = dict(Counter(len(items) for items in subset))
        repeat_source[arm] = sum(len({item["source_id"] for item in items}) < len(items)
                                 for items in subset)
    paired = [uid for uid in cards if all((uid, arm) in plans for arm in experiment["ARMS"])]
    return {
        "verified_review_wires": len(jobs),
        "verified_actor_wires": len(plans),
        "paired_test_outputs": len(paired),
        "paired_identical_tests": sum(
            plans[uid, "ORDINARY"] == plans[uid, "DRAFT_BLIND"] for uid in paired
        ),
        "test_counts_by_arm": counts,
        "review_outputs_with_repeated_source": repeat_source,
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
