"""Verify archived PersistBench controls and produce matched tables for the expanded run."""
import argparse
from collections import Counter
import json

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
    parser.add_argument("action", choices=("controls", "results"))
    cases, scores = load_controls()
    if parser.parse_args().action == "controls":
        print(json.dumps(Counter(method for _, method in scores), indent=2))
    else:
        results = read(HERE / "persist_performance_v1" / "RESULTS.json")
        scores.update({(row["uid"], row["method"]): row["score"] for row in results["rows"]
                       if row["score"] is not None})
        print(json.dumps(summary(cases, scores), indent=2))
