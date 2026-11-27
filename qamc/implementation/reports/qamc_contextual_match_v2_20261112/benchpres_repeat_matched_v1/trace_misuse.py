"""Replay paired BenchPreS misuse labels and report literal nickname presence separately."""

import argparse
from collections import Counter, defaultdict
import json
import re

import run_qamc_benchpres_three_draw as run
from qamc.common import parse_object, sha
from qamc.pa.core import digest
from report_qamc_benchpres_three_draw import metric_values
from trace_nonbold import response


NICKNAME = re.compile(r'\bcalled\s+["“]([^"”]+)["”]', re.I)
CATEGORIES = (
    ("nickname", re.compile(r"\b(?:nicknames?|called)\b", re.I)),
    ("emoji", re.compile(r"\bemojis?\b", re.I)),
    ("expressive_tone", re.compile(r"\bemotionally expressive tone\b", re.I)),
)


def jobs(area, name):
    units = run.read(area / f"{name}_MANIFEST.json")["units"]
    index = {}
    for job in units:
        unit = job["unit"]
        key = unit["root_id"], unit["method"], unit["replicate"], unit["stage"]
        index[key] = job
    if len(units) != len(index):
        raise ValueError("Duplicate manifest unit")
    return index


def audit(waves):
    plan = run.read(run.RUN / "PLAN_PRIVATE.json")
    run.valid(plan)
    if sha(plan) != run.read(run.OUT / "PREFLIGHT.json")["plan_sha256"]:
        raise ValueError("Private plan differs from committed preflight")
    cases = {c["uid"]: c for c in plan["cases"]}
    counts = {m: defaultdict(Counter) for m in run.METHODS}
    repeats = {m: defaultdict(Counter) for m in run.METHODS}
    paired_draws = 0
    for wave in waves:
        area = run.RUN / f"wave-{wave}"
        roots = set(plan["waves"][wave])
        refs = {uid: run.read(run.ROOT / cases[uid]["evaluation_path"]) for uid in roots}
        if any(cases[uid]["independent_confirmation"] or digest(ref) != cases[uid]["evaluation_hash"]
               for uid, ref in refs.items()):
            raise ValueError("Expected frozen exposed development evaluation")
        rows = run.read(area / "RESULTS.json")
        settled = {(r["uid"], r["method"], r["replicate"]): r["score"] for r in rows}
        expected = {(uid, method, draw) for uid in roots
                    for method in run.METHODS for draw in run.REPEATS}
        if len(rows) != len(settled) or set(settled) != expected:
            raise ValueError("Unexpected settlement allocation")
        actors, judges = jobs(area, "ACTOR"), jobs(area, "JUDGE")
        for uid, ref in sorted(refs.items()):
            for draw in run.REPEATS:
                scores = {m: settled[uid, m, draw] for m in run.METHODS}
                if not all(scores.values()):
                    continue
                paired_draws += 1
                for m, score in scores.items():
                    metric_values(score, ref)
                    answer = response(area, "generation", actors[uid, m, draw, "Actor"])
                    for i, d in enumerate(score["decisions"]):
                        if d["appropriate"]:
                            continue
                        pref = d["preference"]
                        judge = judges[uid, m, draw, f"BenchAttr{i}"]
                        packet = json.loads(judge["request"]["messages"][-1]["content"])
                        returned = parse_object(response(area, "grading", judge))["label"]
                        if packet["response"] != answer or packet["preference"] != pref or returned != d["label"]:
                            raise ValueError("Actor and Judge records differ from settled evaluation")
                        category = next((key for key, pat in CATEGORIES if pat.search(pref)), "other")
                        follow = int(d["label"] == "follow")
                        counts[m][category].update(inappropriate_positions=1, judge_misuses=follow)
                        repeats[m][uid, i].update(scored_draws=1, misuse_draws=follow)
                        quoted = NICKNAME.search(pref)
                        if category == "nickname" and quoted:
                            literal = bool(re.search(r"(?<!\w)" + re.escape(quoted[1]) + r"(?!\w)", answer))
                            outcome = f"judge_{'follow' if follow else 'reject'}_literal_{'yes' if literal else 'no'}"
                            counts[m][category].update(quoted_nickname_positions=1, **{outcome: 1})
    summary = {}
    for m in run.METHODS:
        hist = Counter(f"{r['misuse_draws']}_of_{r['scored_draws']}"
                       for r in repeats[m].values() if r["misuse_draws"])
        summary[m] = {"by_attribute": counts[m], "recurrence_per_misused_task_attribute": hist}
    return {"waves": waves, "paired_task_draws": paired_draws, "methods": summary,
            "nickname_match": "case-sensitive word boundary", "score_changes": 0, "model_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wave", type=int, choices=range(6), nargs="+", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(sorted(set(args.wave))), indent=2, sort_keys=True))
