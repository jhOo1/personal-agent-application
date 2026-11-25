"""Recover the archive's exact GPT-4.1 C5 grades without new evaluation."""
import json
from pathlib import Path

from qamc.common import sha
import transfer_edit as transfer
from transfer_execution import EVALUATOR, grading_jobs

HERE = Path(__file__).resolve().parent
C5 = "GOAL_EFFECT_GEPA"
METRICS = ("failure_release", "failure_strict_utility")


def main():
    board = "PersistBench"
    cases, protocol, controls = transfer.context(board)
    archive = transfer.archived_answers(board, cases)
    c5 = {r["uid"]: r for r in archive if r["method"] == C5 and r["actor_status"] == "OK"}
    frozen = {r["uid"]: r["score"] for r in controls if r["method"] == C5}
    exact, conflicts = transfer.matching_grading_receipts(board, cases, protocol, archive)
    wires, _ = grading_jobs(board, list(c5.values()), cases, protocol)
    rows, missing = [], []
    for (uid, _, stage), wire in wires.items():
        digest = sha(wire)
        if digest not in exact or digest in conflicts:
            missing.append({"uid": uid, "request_sha256": digest,
                            "reason": "ambiguous" if digest in conflicts else "not_archived"})
            continue
        if stage != transfer.persist.STAGE or frozen[uid] is None:
            raise ValueError("Aligned C5 grade is missing")
        category = cases[uid]["category"]
        result = EVALUATOR.score(category, exact[digest])
        flags = {name: result[name] for name in METRICS}
        if flags != {name: frozen[uid][name] for name in METRICS}:
            raise ValueError("C5 historical scores changed")
        rows.append({"uid": uid, "category": category, "judge_request_sha256": digest,
                     "answer_sha256": sha(c5[uid]["answer"]), **flags})
    result = {"model": protocol["model"], "rows": rows, "missing": missing, "new_calls": 0}
    (HERE / "PERSIST_C5_EXACT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")


if __name__ == "__main__":
    main()
