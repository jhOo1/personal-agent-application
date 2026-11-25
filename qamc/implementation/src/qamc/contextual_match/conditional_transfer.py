"""Development prototype: test scope transport without another model call.

One prediction supplies identical original-source/note inputs to both arms.
Only the guarded arm excludes a predicted conditional means whose supporting
purpose is contradicted by the current task. UNKNOWN never means rejection.
This is a testable heuristic, not causal identification or semantic proof.
"""
from copy import deepcopy
import json

from qamc.common import parse_object
from . import behavioral_probes, selection_codec_v2
from .core import normalize_selection

POLICY = "conditional_means_transport_v1"
ROLES = {"END_OR_TASTE", "CONTINUING_CONSTRAINT", "CONDITIONAL_MEANS", "OTHER_OR_MIXED"}
MATCHES = {"MATCHED", "CONTRADICTED", "UNKNOWN", "NOT_REQUIRED"}
INSTRUCTION = """
Replace the final output interface with exactly preference_actions,
unresolved_ids, use_bounds, transfer_checks. Keep all previous selection and
source requirements. transfer_checks is a map with exactly the retained memory
IDs as keys. Each value has exactly role, match, source_anchor, task_anchor.

role: END_OR_TASTE for an intrinsically valued outcome or soft taste;
CONTINUING_CONSTRAINT for a continuing prohibition/requirement;
CONDITIONAL_MEANS only when the original makes the criterion instrumental to a
particular activity, beneficiary or purpose; OTHER_OR_MIXED otherwise. A place
where a preference was observed is not automatically its exclusive scope.
Do not call a taste instrumental merely because a reason is given. A belief
about the world does not establish its truth or priority for another person.

match: MATCHED if the current task supports that instrumental purpose or an
explicitly transferable purpose in the source; CONTRADICTED only when the
proposed influence depends on that purpose and the current task instead has a
different purpose without a source-supported bridge; UNKNOWN if unresolved;
NOT_REQUIRED for non-instrumental sources. CONDITIONAL_MEANS cannot have
NOT_REQUIRED. All other roles must have NOT_REQUIRED. For each retained source,
source_anchor is an exact nonempty substring of that original memory. For a
MATCHED or CONTRADICTED decision, task_anchor is an exact nonempty substring of
query or current_context. For the other states task_anchor must be null.

Test whether the source describes an end or only one means of reaching another
end. Preserve optional legitimate preferences and hard/negative constraints.
Do not require usefulness to be necessity. Do not label an unresolved case
CONTRADICTED to simplify the decision. If a single indivisible span mixes an
applicable taste and a condition-limited observation, use OTHER_OR_MIXED unless
the entire proposed influence really depends on the incompatible purpose.
Keep a source in the unguarded proposal if some useful influence remains;
the deterministic guard is an independent diagnostic of predicted transport.
Never output an answer, label strength, UID, benchmark identity or source not
in the supplied public inputs. Anchors certify spelling only, not meaning.
"""


def selector_request(task, prompts):
    empty = [{"memory_id": m, "status": "UNISSUED", "answer": None}
             for m in [None, *[x.memory_id for x in task.memories]]]
    body = behavioral_probes.selector_request(task, prompts, empty, "STRONG_NO_PROBES")
    body["messages"][0]["content"] += INSTRUCTION
    return body


def actor(task, raw, prompts, guarded):
    if type(guarded) is not bool:
        raise ValueError("Explicit OFF/ON arm required")
    obj = parse_object(raw)
    if not isinstance(obj, dict) or set(obj) != {"preference_actions", "unresolved_ids", "use_bounds", "transfer_checks"}:
        raise ValueError("Unexpected transport interface")
    shared = {k: deepcopy(v) for k, v in obj.items() if k != "transfer_checks"}
    # Use the same literal codec and strict compiler in every arm.
    baseline = selection_codec_v2.actor(task, json.dumps(shared, ensure_ascii=False), prompts)
    selected = set(baseline["use_bounds"])
    checks = obj["transfer_checks"]
    if not isinstance(checks, dict) or set(checks) != selected:
        raise ValueError("Checks must cover exactly retained originals")
    texts = {m.memory_id: m.text for m in task.memories}
    rejected = []
    for mid, row in checks.items():
        if not isinstance(row, dict) or set(row) != {"role", "match", "source_anchor", "task_anchor"}:
            raise ValueError("Invalid transfer check")
        role, match = row["role"], row["match"]
        if role not in ROLES or match not in MATCHES:
            raise ValueError("Unknown transfer state")
        anchor = row["source_anchor"]
        if not isinstance(anchor, str) or not anchor.strip() or anchor not in texts[mid]:
            raise ValueError("Source anchor mismatch")
        conditional = role == "CONDITIONAL_MEANS"
        if conditional == (match == "NOT_REQUIRED"):
            raise ValueError("Role/match disagreement")
        task_anchor = row["task_anchor"]
        if match in {"MATCHED", "CONTRADICTED"}:
            if not isinstance(task_anchor, str) or not task_anchor.strip() or not any(
                    task_anchor in text for text in [task.query, task.current_context]):
                raise ValueError("Task anchor mismatch")
        elif task_anchor is not None:
            raise ValueError("Unknown/not-required must not invent task evidence")
        if conditional and match == "CONTRADICTED":
            rejected.append(mid)
    if guarded and rejected:
        chosen = deepcopy(baseline["codec_audit"]["normalized_selector"])
        chosen["preference_actions"] = [
            {"memory_id": a["memory_id"], "decision": "DROP"} if a["memory_id"] in rejected else a
            for a in chosen["preference_actions"]]
        chosen["use_bounds"] = {k: v for k, v in chosen["use_bounds"].items() if k not in rejected}
        built = selection_codec_v2.actor(task, json.dumps(chosen, ensure_ascii=False), prompts)
    else:
        built = baseline
    normalize_selection(task, built["selection"])
    return {**built, "transfer_audit": {"policy": POLICY, "guarded": guarded,
        "checks": deepcopy(checks), "predicted_rejections": rejected,
        "executed_rejections": rejected if guarded else [],
        "unknown_is_drop": False, "semantic_correctness_proven": False}}
