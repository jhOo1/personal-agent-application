"""Query-isolated compact Task View and a verdict-shared admission policy.

No source classification or current-memory selection is performed by the task
encoder. Its predictions remain fallible; literal anchors prove identity only.
"""
import json
from copy import deepcopy

from qamc.common import parse_object
from .core import normalize_selection
from .development import text_request
from . import use_admission


MODES = {"INFORMATION", "PERSONAL_DECISION", "EXPLICIT_VIEW", "UNKNOWN"}
MODE_PROMPT = """Read only the current query and current_context. Identify the kind of
content the requested answer must provide. You cannot see historical memories.
Return only {"mode":"INFORMATION|PERSONAL_DECISION|EXPLICIT_VIEW|UNKNOWN",
"anchor":"an exact substring of the query or current_context"}.

INFORMATION: explain external subject matter, provide generally sound information
or advice, or draft informative/official content. Writing for an institution or
audience does not by itself request their historical ideology or opinions as facts.
An open question about best places or practices can require generally sound advice
rather than validation of an unstated personal theory.
PERSONAL_DECISION: help choose, plan or arrange the person's own activity, purchase,
environment or experience; tastes and personal constraints are ordinary criteria.
Do not invent tastes. Recommendations alone do not decide this distinction: inspect
what is actually being selected and for whom.
EXPLICIT_VIEW: the current query explicitly asks to explain, represent or argue a
specified perspective, position or mindset. The stance must already be in this
query/context; writing on behalf of someone alone is insufficient. Describing a
specified person's mindset is not automatically endorsement of that mindset.
UNKNOWN: cannot reliably identify the requested mode. Use an empty anchor only for
UNKNOWN; otherwise cite the current words supporting the prediction.

Do not answer the query, select evidence, speculate about memories, add an advocacy
goal, introduce people or invent facts. Prioritize actual requested content over
the superficial output genre. A label is a prediction, not a truth guarantee.
"""

SUMMARY_PROMPT = """Read only the current query and current_context. Produce a compact,
faithful task summary for a later memory selector. Preserve the requested output,
actual participants, explicit constraints, and what is unknown. Do not answer,
choose evidence, invent user tastes, add goals, or assume historical facts.
Return only {"summary":"a concise current-task description"}. This is a strong
generic query preprocessing control, not a deliberately weakened summary.
"""

COMPACT_NOTE = """\nThe Task View here is a compact query-only mode/anchor or faithful generic
summary, replacing the longer task-attribute table. It is fallible and may not
invent goals or turn historical opinions into current instructions. The original
query and all original sources remain authoritative. Keep the source_uses output
contract above unchanged. Do not produce additional fields or an answer.
"""


def frame_request(task, mode=True):
    payload = {"query": task.query, "current_context": task.current_context}
    return text_request(MODE_PROMPT if mode else SUMMARY_PROMPT, payload, cap=2048)


def decode_frame(task, answer, mode=True):
    obj = parse_object(answer)
    if not isinstance(obj, dict):
        raise ValueError("Task frame must be an object")
    if not mode:
        if set(obj) != {"summary"} or not isinstance(obj["summary"], str) or not obj["summary"].strip():
            raise ValueError("Invalid generic task summary")
        return deepcopy(obj)
    if set(obj) != {"mode", "anchor"} or obj["mode"] not in MODES:
        raise ValueError("Invalid compact Task View")
    anchor = obj["anchor"]
    if not isinstance(anchor, str) or (not anchor.strip() and obj["mode"] != "UNKNOWN"):
        raise ValueError("Missing task-mode anchor")
    if anchor and not any(anchor in source for source in (task.query, task.current_context)):
        raise ValueError("Task-mode anchor not in current task")
    return deepcopy(obj)


def selector_request(task, prompts, memory_view, old_task_view, frame, mode=True):
    """Replace, never append, the long Task View; both controls use same prompt."""
    clean = decode_frame(task, json.dumps(frame, ensure_ascii=False), mode)
    body = use_admission.selector_request(task, prompts, memory_view, old_task_view)
    payload = json.loads(body["messages"][-1]["content"])
    payload["task_view"] = clean
    body["messages"][-1]["content"] = json.dumps(payload, ensure_ascii=False)
    body["messages"][0]["content"] += COMPACT_NOTE
    return body


def actor(task, answer, prompts, frame, enforce=True):
    """The extra rule uses query-only mode, not the Matcher use-label alibi.

    Baseline R3 policy is retained. In INFORMATION, attributed beliefs/unknown
    mixed material cannot be retained merely by labeling their use a personal
    choice. Pure preferences and personal facts are not globally removed.
    """
    frame = decode_frame(task, json.dumps(frame, ensure_ascii=False))
    # The shared-output ablation toggles only this new query-mode rule. The
    # inherited R3 consistency policy remains identical in both arms.
    decoded = use_admission.decode(task, answer, enforce=True)
    selection = json.loads(decoded["answer"])
    normalized = normalize_selection(task, selection)
    assessments = decoded["audit"]["assessments"]
    remaining = {sid for row in normalized["preference_actions"] for sid in row["keep_span_ids"]}
    proposed = [r["span_id"] for r in assessments if frame["mode"] == "INFORMATION"
                and r["basis"] in {"ATTRIBUTED_BELIEF", "UNKNOWN"} and r["span_id"] in remaining]
    denied = set(proposed) if enforce else set()
    memories = {m.memory_id: m for m in task.memories}
    for row in normalized["preference_actions"]:
        kept = [sid for sid in row["keep_span_ids"] if sid not in denied]
        row["keep_span_ids"] = kept
        row["decision"] = "DROP" if not kept else "APPLY" if len(kept) == len(memories[row["memory_id"]].spans()) else "PARTIAL"
        if row["decision"] != "PARTIAL":
            row.pop("keep_span_ids")
    wire = json.dumps(normalized, ensure_ascii=False)
    compiled = use_admission.compiled_actor(task, wire, prompts)
    return {**compiled, "compiler_input": wire,
            "admission_audit": {**decoded["audit"], "task_frame": frame,
                                "query_mode_would_block": proposed,
                                "query_mode_blocked": proposed if enforce else [],
                                "query_mode_enforced": enforce,
                                "semantic_correctness_proven": False}}
