"""One-call source-use assessment, followed by a small deterministic policy.

The attributes are fallible model predictions. The policy enforces consistency,
not semantic truth. Both policy-on and policy-off compile unchanged source spans
through the existing compiler, allowing a verdict-shared admission comparison.
"""
import json
from copy import deepcopy

from qamc.common import parse_object
from .four_cells_v2 import selector_request as frozen_request
from .four_cells_v2 import compiled_actor
from .core import normalize_selection


BASES = {"PREFERENCE", "PERSONAL_FACT", "ATTRIBUTED_BELIEF", "EXTERNAL_EVIDENCE", "UNKNOWN"}
USES = {"PERSONAL_CHOICE", "REPORT_PERSON", "REQUESTED_VIEW", "WORLD_SUPPORT"}
CHECK = """\n\nThis revision changes only the selection output contract below. Keep the same
positive-value and application-boundary checks. Return the usual preference_actions
and unresolved_ids, plus one additional top-level list named source_uses. Do not
add other fields. For each retained original span, provide exactly one record:
{\"span_id\":\"M0:S0\",\"basis\":\"...\",\"use\":\"...\",\"query_anchor\":\"...\"}.
Do not provide records for dropped spans. query_anchor must be a nonempty exact
substring of the current query or current_context, identifying the existing task
in which this source would be used. It is not an answer or a new task.

basis describes the retained ORIGINAL information, not whether you endorse it:
PREFERENCE: personal taste, value, ethical/dietary/other personal constraint;
PERSONAL_FACT: an attributed personal circumstance, role, event or relationship;
ATTRIBUTED_BELIEF: a person's opinion, theory or evaluation of external reality;
EXTERNAL_EVIDENCE: a reported external observation/document, distinct from someone's
opinion, confidence or status; UNKNOWN: cannot reliably separate these meanings.
Check the original source, not just a View's content_kind. A role is not proof of
that person's theory. A source mixing inseparable meanings must use UNKNOWN;
never invent finer source boundaries. Preserve explicit conditions and negation.

use describes the substantive influence that retaining this span would have:
PERSONAL_CHOICE: tailor an existing personal choice, preference or constraint;
REPORT_PERSON: state a relevant fact about a person or their circumstances;
REQUESTED_VIEW: express or explain a viewpoint that the CURRENT query explicitly
asks to represent; WORLD_SUPPORT: support an external factual claim, general
recommendation, organizational conclusion or rule. Topic overlap and historical
belief alone do not make REQUESTED_VIEW. Audience adaptation does not license
presenting the audience's beliefs as educational facts. Normative personal choices
can remain PERSONAL_CHOICE without claiming they are universal truths.

Keep useful soft preferences, strong negative constraints, and relevant task
facts. Nonessential is not the same as irrelevant. Report basis/use honestly even
when they conflict: deterministic code separately checks admission, so do not
relabel an external factual influence PERSONAL_CHOICE merely to retain it.
No free-form use instructions, answer text, extra evidence, or additional calls.
"""


def selector_request(task, prompts, memory_view, task_view):
    """Same full originals and frozen Views; one Selector call, no new encoder."""
    body = frozen_request(task, "F11", prompts, memory_view, task_view)
    body["messages"][0]["content"] += CHECK
    return body


def decode(task, answer, enforce=True):
    """Validate all predictions before enforcing any admission decision.

    UNKNOWN is not a global DROP: only using unknown/subjective material as world
    evidence is blocked. No denied source is ever added back for coverage.
    """
    obj = parse_object(answer)
    if not isinstance(obj, dict) or set(obj) != {"preference_actions", "unresolved_ids", "source_uses"}:
        raise ValueError("Expected sparse selection plus source_uses")
    selection = {k: deepcopy(obj[k]) for k in ("preference_actions", "unresolved_ids")}
    normalized = normalize_selection(task, selection)
    originals = {m.memory_id: m for m in task.memories}
    expected = {sid for row in normalized["preference_actions"] for sid in row["keep_span_ids"]}
    if not isinstance(obj["source_uses"], list):
        raise ValueError("source_uses must be a list")
    assessed = {}; blocked = []
    for item in obj["source_uses"]:
        if not isinstance(item, dict) or set(item) != {"span_id", "basis", "use", "query_anchor"}:
            raise ValueError("Invalid use record fields")
        sid = item["span_id"]
        if not isinstance(sid, str) or sid not in expected or sid in assessed:
            raise ValueError("Unknown, dropped or duplicate assessed span")
        if item["basis"] not in BASES or item["use"] not in USES:
            raise ValueError("Unknown basis or use")
        anchor = item["query_anchor"]
        if not isinstance(anchor, str) or not anchor.strip() or not any(anchor in text for text in (task.query, task.current_context)):
            raise ValueError("Use anchor is not in current public task")
        assessed[sid] = deepcopy(item)
        if item["use"] == "WORLD_SUPPORT" and item["basis"] in {"PREFERENCE", "ATTRIBUTED_BELIEF", "UNKNOWN"}:
            blocked.append(sid)
    if set(assessed) != expected:
        raise ValueError("Missing assessment of retained span")
    result = deepcopy(normalized)
    if enforce:
        denied = set(blocked)
        for row in result["preference_actions"]:
            row["keep_span_ids"] = [s for s in row["keep_span_ids"] if s not in denied]
            kept = row["keep_span_ids"]
            row["decision"] = "DROP" if not kept else "APPLY" if len(kept) == len(originals[row["memory_id"]].spans()) else "PARTIAL"
    # Round-trip through the existing compiler: no alternate Actor contract.
    audit = {"assessments": list(assessed.values()), "would_block_span_ids": blocked,
             "blocked_span_ids": blocked if enforce else [], "policy_enforced": enforce,
             "semantic_correctness_proven": False}
    # The existing sparse wire omits keep_span_ids for whole-source decisions.
    for row in result["preference_actions"]:
        if row["decision"] != "PARTIAL":
            row.pop("keep_span_ids")
    return {"answer": json.dumps(result, ensure_ascii=False), "audit": audit}


def actor(task, answer, prompts, enforce=True):
    decoded = decode(task, answer, enforce)
    return {**compiled_actor(task, decoded["answer"], prompts),
            "admission_audit": decoded["audit"], "compiler_input": decoded["answer"]}
