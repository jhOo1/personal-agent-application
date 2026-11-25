"""Trace what an earlier patch experiment can tell us before new dispatch."""
import json
from pathlib import Path

from qamc.common import sha

import decision_edit as edit

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
EARLIER = PARENT / "window_07_fixed_source_application_v1"
EXPOSURE = (
    EARLIER / "ANSWER_CHECKPOINT.json",
    PARENT.parent / "qamc_draft_conditioned_application" / "PILOT.json",
    PARENT / "fixed_answer_choice_rpeval_v44" / "NATIVE_WITNESSES.json",
)


def read(path):
    return json.loads(path.read_text())


def patch_sizes(answers):
    rows = []
    for row in answers:
        if row["method"] != "EVIDENCE_PATCH":
            continue
        wire = row["actor_request"]
        if sha(wire) != row["actor_request_sha256"]:
            raise ValueError("Archived patch request changed")
        units = json.loads(wire["messages"][1]["content"])["draft_units"]
        applied = {action["unit_id"]: action["replacement"] for action in row["compile_audit"]["edits"]}
        base = "".join(unit["text"] + unit["separator"] for unit in units)
        rebuilt = "".join(applied.get(unit["unit_id"], unit["text"]) + unit["separator"] for unit in units)
        if base != row["draft"] or rebuilt != row["answer"]:
            raise ValueError("Archived patch does not reproduce its answer")
        removed = sum(len(unit["text"]) for unit in units if unit["unit_id"] in applied)
        inserted = sum(map(len, applied.values()))
        limits = [name for name, too_large in (
            ("count", len(applied) > edit.MAX_EDITS), ("replaced", removed > len(base) // 2),
            ("inserted", inserted > max(256, len(base) // 2)),
        ) if too_large]
        rows.append({"uid": row["uid"], "benchmark": row["benchmark"], "edits": len(applied),
                     "draft_chars": len(base), "replaced_draft_chars": removed, "inserted_chars": inserted,
                     "new_size_guards_exceeded_on_archived_representation": limits})
    return rows


def audit():
    old_patches, old_full, recent_cases = (read(path) for path in EXPOSURE)
    roots = {r["uid"]: r for r in read(PARENT / "counterfactual_rpeval_v41" / "FROZEN.json")["roots"]}
    inspected = {r["uid"] for r in (*old_patches, *old_full["rows"], *recent_cases) if r["uid"].startswith("rpeval/")}
    groups = {roots[uid]["group"] for uid in inspected & roots.keys()}
    ready = [r for r in read(HERE / "PREFLIGHT.json")["RPEval"]["observed"] if r["group"] not in groups]
    rows = patch_sizes(old_patches)
    return {
        "exposure_sources": {f"{p.parent.name}/{p.name}": sha(p.read_bytes()) for p in EXPOSURE},
        "previous_patch_replay": rows,
        "prior_patch_size_schema_rejections": sum(bool(r["new_size_guards_exceeded_on_archived_representation"])
                                                   for r in rows),
        "diagnostic_uids_absent_from_current_manifest": sorted(inspected - roots.keys()),
        "diagnostic_groups": sorted(groups), "eligible_remaining": len(ready),
        "eligible_remaining_groups": len({r["group"] for r in ready}),
        "new_model_calls": 0, "new_method_scores": 0,
        "note": "Size comparisons use the old paragraph representation. They do not determine acceptance "
                "or scores for a new editor. The excluded groups cover these documented diagnostics only. "
                "The remaining slice is still previously exposed development data.",
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
