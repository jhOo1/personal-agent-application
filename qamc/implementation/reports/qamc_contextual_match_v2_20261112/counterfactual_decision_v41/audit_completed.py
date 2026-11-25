"""Validate paired V41 generation and quantify native Judge-field disputes offline."""
from collections import Counter
import json

from qamc.common import sha
from qamc.pa.core import digest
from qamc_rpeval_terminal_judge_sensitivity import inspect, pair_bounds

from run_v41 import ARMS, FINAL, GATE, NATIVE, OUT, RP, author_cases, baseline, final_requests, formal, read

EDGES = ((ARMS[1], ARMS[0]), (RP, ARMS[0]), (GATE, ARMS[0]), (RP, ARMS[1]))


def checked_manifest(wave, stage, expected, seen):
    manifest = read(wave / (stage + "_MANIFEST.json"))
    physical = {(job["unit"]["root_id"], job["unit"]["method"]): sha(job["request"])
                for job in manifest["units"]}
    actual = dict(physical)
    visible = seen | set(physical.values())
    aliases = read(wave / (stage + "_WIRE_REUSE.json"))
    for alias in aliases:
        key, digest = (alias["uid"], alias["arm"]), alias["sha256"]
        if key in actual or digest not in visible:
            raise ValueError(f"Unresolved {stage} reuse")
        actual[key] = digest
    if actual != expected:
        raise ValueError(f"Actual {stage} manifest differs from replay")
    seen.update(physical.values())
    return len(aliases)


def audited_rows(plan):
    roots = {root["uid"]: root for root in plan["roots"]}
    references = author_cases(read(formal.OUT / "PLAN.json"))
    reviews, scores = set(), set()
    drafts = {}
    counts = Counter()
    for index, uids in enumerate(plan["waves"]):
        wave = OUT / f"wave_{index:02d}"
        if not (wave / "COMPLETED.json").is_file():
            break
        outcome = read(wave / "COMPLETED.json")
        if [row["uid"] for row in outcome["rows"]] != uids:
            raise ValueError("Completed cohort changed")
        drafts.update(read(wave / "DRAFT_RESULTS.json"))
        expected = {}
        for row in outcome["rows"]:
            uid = row["uid"]
            root, ref = roots[uid], references[uid]
            truth = read(formal.ROOT / ref["evaluation_path"])
            labels = truth["intent_type"]
            if (digest(truth) != ref["evaluation_hash"] or len(labels) != len(root["original_sources"])
                    or set(labels) - set("ABC")):
                raise ValueError("Author reference changed")
            task_draft = drafts[root["task_wire_sha256"]]["answer"]
            if task_draft:
                wires = final_requests(root, archived_draft=root["archived"][RP]["answer"], task_only_draft=task_draft)
                a, b = (wires[m] for m in ARMS)
                if a["messages"][1] != b["messages"][1] or a["messages"][0] == b["messages"][0]:
                    raise ValueError("Paired arms differ in user input or share the same instructions")
                expected.update({(uid, arm): sha(wire) for arm, wire in wires.items()})
                if row["trace"]["review_sha256"] != {arm: expected[uid, arm] for arm in ARMS}:
                    raise ValueError("Reported Actor hashes changed")
                counts["shared_input_rows"] += 1
            else:
                counts["shared_draft_missing"] += 1
            row["labels"] = labels
        counts["exact_review_aliases"] += checked_manifest(wave, FINAL, expected, reviews)
        grade_jobs, aliases = baseline.grade_jobs(
            {**plan, "roots": [roots[uid] for uid in uids]},
            {row["uid"]: row["answers"] for row in outcome["rows"]},
        )
        if aliases != read(wave / "GRADE_REUSE.json"):
            raise ValueError("Native answer hash reuse changed")
        grade_expected = {(uid, arm): sha(wire) for uid, arm, wire in grade_jobs}
        counts["exact_grade_aliases"] += checked_manifest(wave, NATIVE, grade_expected, scores)
        counts["answer_only_grade_wires"] += len(grade_expected)
        yield outcome["rows"], counts


def audit():
    plan = read(OUT / "FROZEN.json")
    roots = {root["uid"]: root for root in plan["roots"]}
    counts, row_votes, completed = Counter(), {}, []
    for rows, counts in audited_rows(plan):
        for row in rows:
            uid, labels = row["uid"], row["labels"]
            root = roots[uid]
            completed.append((uid, root["in_sensitivity"], set(labels) == {"A"}, row["group"]))
            for method in (*ARMS, RP, GATE):
                native = row["native"][method]
                if native["fields"].get("match") is None:
                    continue
                answer = (row["answers"][method] if method in ARMS else root["archived"][method])["answer"]
                row_votes[uid, method] = inspect({"uid": uid, "method": method,
                                                "native_fields": native["fields"], "answer": answer,
                                                "raw_scores": {"RPEvalJudge": native["raw"]}}, labels)
    matrices = {}
    for left, right in EDGES:
        stats = {name: Counter() for name in ("all", "reduced_exposure", "additional_groups", "all_A", "contains_BC")}
        groups = {name: set() for name in stats}
        for uid, selected, all_a, group in completed:
            a, b = (row_votes.get((uid, arm)) for arm in (left, right))
            if a is None or b is None:
                continue
            lo, hi = pair_bounds(b, a)
            amount = {"paired_roots": 1, "left_matched": a["matched"], "right_matched": b["matched"],
                      "positions": a["positions"], "lower_delta": lo, "upper_delta": hi,
                      "flagged_roots": bool(a["flags"] or b["flags"])}
            for name in ("all", "reduced_exposure" if selected else "additional_groups",
                         "all_A" if all_a else "contains_BC"):
                stats[name].update(amount)
                groups[name].add(group)
        matrices[f"{left}__{right}"] = {name: {**c, "source_groups": len(groups[name])} for name, c in stats.items()}
    counts["completed_roots"] = len(completed)
    return {"complete": len(completed) == len(roots), "planned_roots": len(roots), "counts": counts,
            "score_changes": 0, "new_model_requests": 0, "pairs": matrices,
            "flagged_cells": [cell for cell in row_votes.values() if cell["flags"]]}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
