"""One deterministic follow-up to R4, using exactly its frozen predictions.

A personal decision is not permission to treat an attributed stance as a
binding selection criterion. Actual preferences/constraints, personal facts,
explicitly requested viewpoints and unresolved task modes are unchanged.
The distinction depends on fallible upstream basis predictions, not truth.
"""
import json

from . import query_mode
from .core import normalize_selection
from .four_cells_v2 import compiled_actor


def actor(task, answer, prompts, frame):
    base = query_mode.actor(task, answer, prompts, frame, enforce=True)
    selection = normalize_selection(task, json.loads(base["compiler_input"]))
    remaining = {sid for row in selection["preference_actions"] for sid in row["keep_span_ids"]}
    denied = [r["span_id"] for r in base["admission_audit"]["assessments"]
              if frame["mode"] == "PERSONAL_DECISION" and r["basis"] == "ATTRIBUTED_BELIEF"
              and r["span_id"] in remaining]
    originals = {m.memory_id:m for m in task.memories}
    for row in selection["preference_actions"]:
        kept = [sid for sid in row["keep_span_ids"] if sid not in denied]
        row["keep_span_ids"] = kept
        row["decision"] = "DROP" if not kept else "APPLY" if len(kept) == len(originals[row["memory_id"]].spans()) else "PARTIAL"
        if row["decision"] != "PARTIAL":
            row.pop("keep_span_ids")
    wire = json.dumps(selection, ensure_ascii=False)
    return {**compiled_actor(task, wire, prompts), "compiler_input":wire,
            "admission_audit":{**base["admission_audit"], "personal_belief_blocked":denied,
                               "semantic_correctness_proven":False}}
