"""Reconcile retained C provenance with frozen IPE-C endpoints. No inference."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def score(record, positions):
    if record is None or record["grade"] is None:
        return None
    grade = record["grade"]
    match = grade.get("match")
    if not match or match["positions"] != positions:
        return None
    return grade


def compare(pairs):
    result = Counter()
    groups = Counter()
    for row, incumbent, task in pairs:
        delta = task["match"]["matched"] - incumbent["match"]["matched"]
        groups[row["source_group"]] += delta
        result.update({
            "questions": 1,
            "positions": len(row["labels"]),
            "ipe_match": incumbent["match"]["matched"],
            "no_history_match": task["match"]["matched"],
            "wins": int(delta > 0),
            "losses": int(delta < 0),
            "ties": int(delta == 0),
            "oracle_gain": max(delta, 0),
        })
        for field in ("OPB", "UPB", "FM"):
            result["ipe_" + field] += incumbent[field]
            result["no_history_" + field] += task[field]
    result.update({
        "groups": len(groups),
        "groups_net_win": sum(delta > 0 for delta in groups.values()),
        "groups_net_loss": sum(delta < 0 for delta in groups.values()),
    })
    return dict(result)


def build(base):
    panel = read(base / "retained_c_realization_v1/PANEL.json")
    pointers = panel["wire_and_availability_index"]
    original = read(base / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
    answers = {r["uid"]: r["answer"] for r in original if r["method"] == "RPR_PAPER_FULL" and r.get("answer")}
    endpoints = read(base / "ipe_c_two_endpoint_completion_v1/RESULTS.json")
    rows = {r["uid"]: r for r in endpoints["rows"]}
    aligned = set()
    targets = 0
    for pointer in pointers:
        uid = pointer["uid"]
        row = rows[uid]
        answer = answers[uid]
        canonical_hash = digest(json.dumps(answer, ensure_ascii=False, separators=(",", ":")))
        if canonical_hash != pointer["answer_sha256"]:
            raise ValueError(f"Retained-C answer mismatch: {uid}")
        if digest(answer) != row["scores"]["RPR_PAPER_FULL"]["answer_sha256"]:
            raise ValueError(f"Endpoint RP answer mismatch: {uid}")
        if row["ipe_c"]["answer_sha256"] == digest(answer):
            aligned.add(uid)
            targets += 1
    pairs, unflagged = [], []
    skipped = Counter()
    for uid in sorted(aligned):
        row = rows[uid]
        incumbent_record, task_record = (row["scores"].get(key) for key in ("IPE_C", "TASK_ONLY"))
        incumbent, task = (score(record, len(row["labels"])) for record in (incumbent_record, task_record))
        if incumbent is None or task is None:
            skipped["missing_pair"] += 1
            continue
        pair = (row, incumbent, task)
        pairs.append(pair)
        if incumbent_record["flags"] == [] and task_record["flags"] == []:
            unflagged.append(pair)
    return {
        "new_model_calls": 0,
        "retained_c_positions": len(pointers),
        "retained_c_questions": len({p["uid"] for p in pointers}),
        "ipe_c_exact_rp_questions": len(aligned),
        "ipe_c_exact_rp_visible_c_positions": targets,
        "skipped": dict(skipped),
        "paired": compare(pairs),
        "paired_without_flags": compare(unflagged),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_root", type=Path)
    print(json.dumps(build(parser.parse_args().report_root), ensure_ascii=False, indent=2))
