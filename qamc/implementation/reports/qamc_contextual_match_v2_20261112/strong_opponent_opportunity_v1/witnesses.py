"""Trace prioritized native overlap cases back to archived tasks and visible answers."""
import json

from qamc.common import sha
from replay_transfer import transfer

from inventory import (
    C5, GATE, GEPA, IPE, PAPER, RP, RUBRIC, ZERO, read, verified_comparison,
)

AREA = "strong_opponent_opportunity_v1"
ORIGINAL_RPE = "counterfactual_rpeval_v41"
TASK_ONLY = "TASK_ONLY"


def exact_answer(answer, digest):
    if not answer or sha(answer) != digest:
        raise ValueError("Stored answer differs from verified score artifact")
    return answer


def rpeval(inventory):
    raw = read(f"{ORIGINAL_RPE}/FROZEN.json")
    roots = {r["uid"]: r for r in raw["roots"]}
    labels = {r["uid"]: r["labels"] for r in read(f"{ORIGINAL_RPE}_task_only/RESULTS.json")["roots"]}
    task_drafts = {}
    for i, _ in enumerate(raw["waves"]):
        task_drafts.update(read(f"{ORIGINAL_RPE}/wave_{i:02d}/DRAFT_RESULTS.json"))
    frontier = {r["uid"]: r["base"] for r in read("selective_path_frontier_v1/RESULTS.json")["rows"]}
    selected, claim = [], {}
    for bucket, rows in inventory["per_case"].items():
        groups = set()
        ranked = sorted(rows, key=lambda r: (-r["best_archive_shortfall"], sha(r["uid"])))
        for row in ranked:
            if row["group"] in groups or not row["best_archive_shortfall"] or row["judge_flags"]:
                continue
            uid = row["uid"]
            root = roots[uid]
            answers = {m: root["archived"][m]["answer"] for m in (GATE, RP)}
            answers[IPE] = answers[RP] if frontier[uid] == RP else task_drafts[root["task_wire_sha256"]]["answer"]
            selected.append({**row, "stratum": bucket, "public_task": root["public_task"],
                             "labels": labels[uid], "original_sources": root["original_sources"],
                             "actual_rp_policy": root["archived_policy"],
                             "answers": {m: exact_answer(a, row["answer_hashes"][m]) for m, a in answers.items()}})
            groups.add(row["group"])
            if len(groups) == 4:
                break
        claim[bucket] = len(groups)
    return {"coverage": claim, "prioritized_cases": selected}


def benchpres(inventory):
    data = verified_comparison()
    cases, scores = data["cases"], data["scores"]
    methods = (GATE, C5, RP)
    archive = {(r["uid"], r["method"]): r for r in transfer.archived_answers("BenchPreS", cases)
               if r["method"] in methods}
    papers = {r["uid"]: r for r in read("benchpres_matched_paper_v1/RESULT_ROWS.json") if r["method"] == PAPER}
    output = []
    for row in inventory["strong_common_flags"]:
        uid = row["uid"]
        if cases[uid]["independent_confirmation"]:
            raise ValueError("Holdout is outside the witness inventory")
        score = scores[uid, GATE]["decisions"][row["index"]]
        if sha(score["preference"]) != row["source_text_sha256"]:
            raise ValueError("Matched archive attribute no longer binds")
        root = data["roots"][uid]
        output.append({**row, "public_task": root["public_task"], "attribute": score,
                       "answers": {m: archive[uid, m]["answer"] for m in methods} | {PAPER: papers[uid]["answer"]}})
    return output


def persistbench(inventory):
    cases, _, _ = transfer.context("PersistBench")
    archive = {(r["uid"], r["method"]): r for r in transfer.archived_answers("PersistBench", cases)
               if r["method"] in (GATE, RP, RUBRIC, GEPA, ZERO)}
    roots = {r["uid"]: r for r in transfer.development_roots("PersistBench")}
    output = []
    for category, details in inventory.items():
        for row in details["per_case"]:
            if not row["strong_common_fail"]:
                continue
            uid = row["uid"]
            potential = archive.get((uid, ZERO))
            answers = {m: exact_answer(archive[uid, m]["answer"], row["answer_hashes"][m])
                       for m in (GATE, RUBRIC, GEPA)}
            if row["public_only_answer_hash"] is not None:
                if not potential:
                    raise ValueError("Task-only score has no verified answer")
                answers[ZERO] = exact_answer(potential["answer"], row["public_only_answer_hash"])
            public = {**roots[uid]["public_task"], "original_sources": roots[uid]["original_sources"]}
            output.append({**row, "category": category, **public, "answers": answers})
    return output


def extract():
    census = read(f"{AREA}/INVENTORY.json")
    return {"rpeval": rpeval(census["rpeval"]), "benchpres": benchpres(census["benchpres"]),
            "persistbench": persistbench(census["persistbench"]), "inventory_sha256": sha(census),
            "new_calls": 0, "original_scores_changed": 0}


if __name__ == "__main__":
    print(json.dumps(extract(), ensure_ascii=False, indent=2, sort_keys=True))
