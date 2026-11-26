"""Verify archived PersistBench controls and produce matched tables for the expanded run."""
import argparse
from collections import Counter, defaultdict
import json
import re

from build_jobs import archive as baseline_archive
from freeze_persist_performance_panel import CONTROLS, HERE, read
from qamc.common import sha
from transfer_execution import grading_jobs
from transfer_replay import RUNS, persist, saved_scores

METHODS = ("PB_RUBRIC", "PB_GEPA", "PB_FILTER_NATIVE", "PB_FILTER_COMMON")
CANDIDATES = ("SELECTED_GEPA", "SELECTED_RUBRIC")


def accepted(controls, context, protocol, receipts):
    scores = {}
    for row in controls:
        uid, method = row["uid"], row["method"]
        score = row["score"]
        if score is None:
            continue
        request, = grading_jobs("PersistBench", [row], context, protocol)[0].values()
        receipt = receipts[uid, method]
        if (sha(request) != receipt["request_sha256"]
                or row["raw_scores"][persist.STAGE] != receipt["response"]["answer"]):
            raise ValueError(f"Archived grade does not match request: {uid}/{method}")
        if (uid, method) in scores:
            raise ValueError(f"Duplicate author result: {uid}/{method}")
        scores[uid, method] = score
    return scores


def load_controls():
    panel = read(HERE / "PERSIST_PERFORMANCE_PANEL.json")
    cases = {r["uid"]: r for r in panel["cases"]}
    context, protocol, _ = baseline_archive.transfer.context("PersistBench")
    receipts = saved_scores(RUNS / persist.AUTHOR_OUT.name / "gpt41")
    rows = [row for path in sorted((CONTROLS / "waves").glob("[0-9][0-9].json"))
            for row in read(path)["rows"] if row["uid"] in cases and row["method"] in METHODS]
    scores = accepted(rows, context, protocol, receipts)
    return cases, scores



def check_actor_pairs(cases):
    manifest = read(HERE / "persist_performance_v1" / "FinalActor_MANIFEST.json")
    pairs = defaultdict(dict)
    for item in manifest["units"]:
        unit, request = item["unit"], item["request"]
        uid, method = unit["root_id"], unit["method"]
        if uid not in cases or method not in CANDIDATES or method in pairs[uid]:
            raise ValueError(f"Unexpected Actor row: {uid}/{method}")
        pairs[uid][method] = request
    counts = {k: Counter() for k in {row["category"] for row in cases.values()}}
    for uid, pair in pairs.items():
        left, right = (pair[method] for method in CANDIDATES)
        a, b = (re.findall(r"<memories>\n(.*?)\n</memories>", request["messages"][0]["content"], re.S)
                for request in (left, right))
        if len(a) != 1 or a != b or left["messages"][1:] != right["messages"][1:]:
            raise ValueError(f"Paired evidence or task drift: {uid}")
        left_settings, right_settings = ({k: v for k, v in request.items() if k != "messages"}
                                         for request in (left, right))
        if left_settings != right_settings:
            raise ValueError(f"Paired Actor settings drift: {uid}")
        count = counts[cases[uid]["category"]]
        count["paired"] += 1
        count["empty_history"] += not a[0]
    return counts


def summary(cases, scores):
    report = {}
    for left, right in [(a, b) for a in CANDIDATES for b in METHODS] + [CANDIDATES]:
        paired = {}
        for uid, case in cases.items():
            category = case["category"]
            totals = paired.setdefault(category, Counter())
            totals["planned"] += 1
            if (uid, left) not in scores or (uid, right) not in scores:
                totals["missing"] += 1
                continue
            flag = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
            a, b = (not scores[uid, method][flag] for method in (left, right))
            totals.update({"paired": 1, "left_pass": a, "right_pass": b,
                           "left_wins": a and not b, "right_wins": b and not a})
        report[f"{left}/{right}"] = paired
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("controls", "actors", "results"))
    cases, scores = load_controls()
    action = parser.parse_args().action
    if action == "controls":
        print(json.dumps(Counter(method for _, method in scores), indent=2))
    elif action == "actors":
        print(json.dumps(check_actor_pairs(cases), indent=2, sort_keys=True))
    else:
        results = read(HERE / "persist_performance_v1" / "RESULTS.json")
        scores.update({(row["uid"], row["method"]): row["score"] for row in results["rows"]
                       if row["score"] is not None})
        print(json.dumps(summary(cases, scores), indent=2))
