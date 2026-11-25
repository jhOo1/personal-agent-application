"""Analyze score and answer changes in the settled same-Actor RPEval comparison."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_asymmetric_fusion as run


def pair(rows, left, right):
    match = run.replay.paired(rows, left, right)
    common = set(match["valid_uids"])
    valid = [row for row in rows if row["uid"] in common]
    return {"match": match, **{metric: run.scorer.comparisons.grade_pair(valid, left, right, metric)
                              for metric in run.active.METRICS}}


def audit():
    state = run.read(run.OUT / "RUN_STATE.json")
    path = run.OUT / "SETTLED.json"
    saved, frozen = run.read(path), run.read(run.OUT / "FROZEN.json")
    if state["state"] != "COMPLETE" or len(saved["ledger"]) != state["physical_requests"]:
        raise ValueError("Wait for the frozen comparison to settle")
    prior = run.replay.prior
    original = {root["uid"]: root for root in run.read(prior.OUT / "FROZEN.json")["roots"]}
    strata, transitions, traces = defaultdict(list), Counter(), []
    for row in saved["rows"]:
        uid = row["uid"]
        if uid not in frozen["requests"]:
            continue
        root = original[uid]
        source_ids = [source["memory_id"] for source in root["original_sources"]]
        before, after = row["old_policy"], row["new_policy"]
        if source_ids != [p["memory_id"] for p in before] or source_ids != [p["memory_id"] for p in after]:
            raise ValueError("Misaligned published preference rows")
        if row["actor"][run.BASE]["request_sha256"] != root["archived_actor_sha256"]:
            raise ValueError("Contemporaneous control is not an exact archival prompt replay")
        affected = [(mid, a["policy"], b["policy"], truth)
                    for mid, a, b, truth in zip(source_ids, before, after, row["labels"], strict=True)
                    if a["policy"] != b["policy"]]
        directions = {a < b for _, a, b, _ in affected}
        relative = "mixed" if len(directions) > 1 else "raises_only" if True in directions else "lowers_only"
        strata[relative].append(row)
        strata["all_changed"].append(row)
        transitions.update(f"{truth}/{a}/{b}" for _, a, b, truth in affected)
        outputs = row["outputs"]
        grades = {arm: row["native"][arm]["fields"] for arm in (run.BASE, run.METHOD, run.ARCHIVED)}
        traces.append({
            "uid": uid, "group": row["group"], "affected": affected,
            "same_exact_current_answers": len(outputs) == 2 and outputs[run.BASE] == outputs[run.METHOD],
            "same_original_answer_after_identical_replay": outputs.get(run.BASE) == row["native"][run.ARCHIVED]["answer"],
            "positions": row["positions"],
            "match": {arm: g.get("match", {}).get("matched") for arm, g in grades.items()},
            "severity": {arm: {f: grade.get(f) for f in ("OPB", "UPB", "FM")}
                         for arm, grade in grades.items()},
            "grade_status": {arm: row["native"][arm].get("status", "ARCHIVED") for arm in grades},
        })
    if len(traces) != len(frozen["requests"]):
        raise ValueError("Unaccounted counterfactual Actor requests")
    return {"settled_sha256": sha(path.read_bytes()), "new_model_requests": 0,
            "repeat_same_wire_drift": pair(strata["all_changed"], run.ARCHIVED, run.BASE),
            "policy_transitions": transitions, "strata": {
                part: pair(rows, run.BASE, run.METHOD) for part, rows in strata.items()},
            "traces": traces}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
