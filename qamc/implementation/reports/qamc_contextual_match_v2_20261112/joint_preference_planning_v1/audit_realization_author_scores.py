"""Replay the locked RPEval author aggregator over the latest saved answer grid."""
from collections import Counter
import json
from pathlib import Path

from qamc.common import parse_object, sha
from qamc.contextual_match.rpeval_author_aggregation import replay

import audit_realization_rubric as current


ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "literature/qamc_pa_v1/RPEval/generation_task/eval_multi.py"
LOCK = current.ablation.OUT.with_name("rpeval_author_aggregation_v2") / "SOURCE_LOCK.json"
DIRECT = current.ablation.method.DIRECT
FULL = current.ablation.method.SEGMENTED
MAIN, GATE, RP = current.ARMS
ARMS = (DIRECT, FULL, MAIN, GATE, RP)


def saved_entries():
    _, rows, _ = current.checked()
    realized = {row["uid"]: row for row in rows}
    entries, anomalies = {}, []
    for base, _, retained in current.source_rows():
        uid = base["uid"]
        answers = {**retained, **{arm: realized[uid]["actor"][arm].get("answer") for arm in (DIRECT, FULL)}}
        cells = {}
        for arm in ARMS:
            saved, answer = base["native"][arm], answers[arm]
            raw = saved.get("raw")
            try:
                obj = parse_object(raw) if raw else {}
            except (ValueError, TypeError):
                if saved["fields"]:
                    raise
                obj = {}
            if obj and not answer:
                raise ValueError("A parsed Judge result has no verified answer")
            full = obj.get("full_match")
            if full is not None and type(full) is not bool:
                anomalies.append({"uid": uid, "method": arm, "issue": "non_boolean_full_match", "value": full})
            cells[arm] = {"entry": {"uid": uid, "ground_truth_type": base["labels"],
                                     "generated_reply": answer, "judge_result": obj,
                                     "status": "OK" if answer else "NO_USABLE_ANSWER"},
                          "strict_valid": "match" in saved["fields"]}
        entries[uid] = cells
    if len(entries) != 233:
        raise ValueError("Expected the frozen exposed RPEval panel")
    return entries, anomalies


def make_summary(entries):
    native = replay(ARCHIVE, [cell["entry"] for cell in entries], True)
    return {"assigned": len(entries), "answers": sum(bool(c["entry"]["generated_reply"]) for c in entries),
            "parsed_objects": sum(bool(c["entry"]["judge_result"]) for c in entries),
            "strict_match_available": sum(c["strict_valid"] for c in entries), **native}


def audit():
    code_hash = sha(ARCHIVE.read_bytes())
    if current.ablation.read(LOCK)["files"][str(ARCHIVE.relative_to(ROOT))] != code_hash:
        raise ValueError("Author evaluator differs from the locked source")
    rows, anomalies = saved_entries()
    tables = {arm: make_summary([r[arm] for r in rows.values()]) for arm in ARMS}
    pairs = {}
    author_subgroups = {}
    strict_rows = current.ablation.read(current.ablation.OUT / "SETTLED.json")["rows"]
    labels = {row["uid"]: row["labels"] for row in strict_rows}
    for reference in (DIRECT, FULL, GATE, RP):
        ids = [uid for uid, cells in rows.items() if all(cells[arm]["strict_valid"] for arm in (reference, MAIN))]
        pair = {arm: make_summary([rows[uid][arm] for uid in ids]) for arm in (reference, MAIN)}
        stats = [pair[arm]["author_summary"] for arm in (reference, MAIN)]
        if stats[0]["nm_sum_m"] != stats[1]["nm_sum_m"]:
            raise ValueError("Strict common Match subset has differing author tuple denominators")
        paired_metric = current.ablation.parent.joint.parent.comparisons.grade_pair
        pairs[reference] = {"common_strict_match_roots": len(ids), "uids": ids, "author": pair,
                            "strict_full_match_pair": paired_metric(strict_rows, reference, MAIN, "full_match")}
        results = {}
        for name in ("all_A", "has_BC"):
            cohort = [uid for uid in ids if (set(labels[uid]) == {"A"}) == (name == "all_A")]
            results[name] = {arm: make_summary([rows[uid][arm] for uid in cohort])
                             for arm in (reference, MAIN)}
        author_subgroups[reference] = results
    paths = (
        ARCHIVE, LOCK, Path(__file__).resolve(), current.ablation.OUT / "SETTLED.json",
        current.ablation.parent.OUT / "SETTLED.json",
    )
    return {"all_assigned": tables, "strict_common": pairs, "raw_full_match_anomalies": anomalies,
            "strict_match_subgroups": author_subgroups,
            "anomaly_counts": Counter(r["method"] for r in anomalies),
            "input_hashes": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths},
            "scores_modified": 0, "model_calls": 0, "independent_confirmation": False}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
