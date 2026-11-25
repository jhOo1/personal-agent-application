"""Inventory executable candidate conflicts in existing exposed RPEval traces."""
from collections import Counter
import json

from qamc.common import sha

import run_asymmetric_fusion as fusion


def grounded_trace(row):
    execution = row["execution"]
    answers = execution.get("answers") or {}
    conflicts = []
    for decision, matrix in (execution.get("matrices") or {}).items():
        generic = answers.get("MODEL_PLACEMENT", {}).get("decisions", {}).get(decision, {})
        for option, entry in matrix["entries"].items():
            witnesses = [witness for witness in entry["checks"].values()
                         if witness["predicted"] == "CONFLICT" and witness["exact_witness"]]
            if witnesses:
                conflicts.append({"decision": decision, "option": option, "witnesses": witnesses,
                                  "already_excluded": option in generic.get("excluded", []),
                                  "actually_shown": option in generic.get("shown", [])})
    visible = [answers.get(arm, {}).get("answer")
               for arm in ("MODEL_PLACEMENT", "STATUS_MATRIX", "GROUNDED_MATRIX")]
    return {"candidate_conflicts": conflicts, "has_matrix": bool(execution.get("matrices")),
            "all_three_answers_identical": all(visible) and len(set(visible)) == 1}


def audit():
    parent = fusion.OUT.parent
    inputs = {
        "panel": fusion.OUT / "SETTLED.json",
        "joint": parent / "joint_preference_planning_rpeval_v1" / "SETTLED.json",
        "grounded": parent / "grounded_feasibility_rpeval_v1" / "SETTLED.json",
    }
    documents = {name: fusion.read(path) for name, path in inputs.items()}
    tasks = {row["uid"]: row["public_task"]
             for row in fusion.read(fusion.replay.prior.OUT / "FROZEN.json")["roots"]}
    roster = {row["uid"]: row["group"] for row in documents["panel"]["rows"]}
    joint = {row["uid"]: row["planning"] for row in documents["joint"]["rows"]}
    grounded = {row["uid"]: grounded_trace(row) for row in documents["grounded"]["rows"]}
    if not roster.keys() <= tasks.keys() or set(joint) != set(tasks):
        raise ValueError("Candidate inventory is outside the archived public roster")
    panels = {}
    for name, group_by_uid in (("118", roster), ("233", {r["uid"]: r["group"] for r in documents["joint"]["rows"]})):
        counts, groups, task_hashes = Counter(), {}, {}
        rows = []
        for uid, group in group_by_uid.items():
            result = joint[uid]
            plan = result.get("plan") or {}
            hard = [clause for clause in plan.get("hard", []) if len(clause["choices"]) == 1]
            low = grounded.get(uid)
            task = tasks[uid]
            indicators = {
                "nonempty_public_facts_or_context": bool(task["facts"] or task["current_context"]),
                "valid_joint_plan": result["status"] == "OK",
                "joint_predicts_unary_hard": bool(hard),
                "joint_predicts_memory_unary_hard": any(c["source_id"] != "TASK" for c in hard),
                "joint_predicts_soft": bool(plan.get("soft")),
                "joint_selected_combination_has_conflict": bool((result.get("solver") or {}).get("control_conflicts")),
                "grounded_matrix": bool(low and low["has_matrix"]),
                "grounded_has_exact_conflict": bool(low and low["candidate_conflicts"]),
                "grounded_conflict_shown_by_generic": bool(
                    low and any(c["actually_shown"] for c in low["candidate_conflicts"])),
            }
            rows.append({"uid": uid, "group": group, "task_sha256": sha(task), "indicators": indicators,
                         "grounded": low})
            for flag, present in indicators.items():
                counts[flag] += int(present)
                if present:
                    groups.setdefault(flag, set()).add(group)
                    task_hashes.setdefault(flag, set()).add(sha(task))
        panels[name] = {"assigned": len(group_by_uid), "source_groups": len(set(group_by_uid.values())),
                        "counts": {flag: {"histories": count, "tasks": len(task_hashes.get(flag, ())),
                                          "groups": len(groups.get(flag, ()))} for flag, count in counts.items()},
                        "rows": rows}
    return {"inputs": {name: sha(path.read_bytes()) for name, path in inputs.items()},
            "new_model_requests": 0, "labels_or_grades_used_to_select": False,
            "syntactic_source_anchors_only": True, "panels": panels}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
