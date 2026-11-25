"""Versioned initialization prompts; not claims of validated optimal behavior."""
import json
from .core import SCHEMA, ARMS, memory_payload, task_payload, matching_payload

FIELD = ('An AttributedField is {"value": <short value or null>, '
         '"status": "EXPLICIT|INFERRED|UNKNOWN", "evidence": [EvidenceRef]}. '
         'EvidenceRef is {"source_id": "...", "start": 0, "end": 10, "quote": "..."}; '
         'offsets are Python Unicode codepoint offsets, end exclusive. Exact source substring '
         'must equal quote. UNKNOWN requires null value and empty evidence. '
         'All other fields require supporting citations; inference is not guaranteed truth.')

MEMORY = """Annotate the supplied allowed historical snapshot without knowing the current query.
Preserve original meaning and actual speaker. Encode subjects, content kind, properties,
negation, conditions, temporal scope, attributed beliefs and explicit entity relations.
Distinguish observed_context (where a statement occurred) from explicit_scope (where the
source restricts its applicability). A restaurant conversation does not itself restrict a
preference to that restaurant. Unknown scope is not global scope or invalidity.
Do not predict current use, APPLY/DROP, answers, task plans or recipient expectations.
Do not convert beliefs into facts, strong tastes into universal constraints, or new interests
into replacement of older interests. Source attributes are fallible aids, not replacements.
Return only {"schema":"contextual_match_v1","sources":[MemoryView]}.
Every supplied source must appear once, preserving source_id and supplied source_sha256.
MemoryView fields are source_id, source_sha256, subject, content_kind, properties,
observed_context, explicit_scope, relations. subject/content_kind are AttributedFields;
the other four attribute collections are lists of AttributedFields. Empty lists are allowed.
Use neutral supplied source IDs only, do not add free-form schema fields.
""" + FIELD

TASK = """Read only the current request and its public current context. Identify existing
deliverables, supported roles, constraints and history-dependent unresolved references.
Do not answer, select memories, add goals, infer personal tastes or assume the requester
participates in every activity. Leave unresolved historical references unresolved.
Return only {"schema":"contextual_match_v1","deliverables":[],"roles":[],
"constraints":[],"unresolved_mentions":[]}, each list containing AttributedFields.
TASK_IMPLIED is additionally allowed for ordinary task-implied dimensions; cite the query
supporting this inference. Anchors may only use source_id query or current_context.
""" + FIELD

SUMMARY = """Summarize only the supplied allowed historical snapshot for a later assistant.
You do not know its current query. Preserve user conditions, strong constraints, useful soft
preferences, subjects, actual attribution, negation, updates and their reasons. Preserve
entity relations and conditions necessary to interpret other memories. Do not predict a
current task or recommend answers. Return only {"summary":"..."}. This is a strong general
preprocessing control using the same output cap as the attribute encoder; do not artificially
compress to an inferior budget or convert beliefs into external facts.
"""

ATTR_HINT = """\nSidecars are fallible source-grounded aids. Read full original sources as authority.
An observed context is not an exclusive scope restriction. UNKNOWN does not itself mean
inapplicable. Do not treat attributed beliefs as independent proof of world facts.
"""

TYPED = """\nFor every original source, assess directed applicability within the unchanged request:
actual subject -> supported participant/beneficiary/recipient -> existing decision ->
conditions/time/negation -> evidential qualification. Topic agreement cannot cancel an
unsupported role or explicit conflict. Useful soft preferences need not be necessary.
Preserve implicit constraints and joint conditions; do not invent participants or new goals.
Do not rank candidate answers or propose a response. Use the original query and sources as
authority over both representations. A prior personal stance is not world evidence.

Return only {"selection": <the original sparse selection object>, "audit_links": [...],
"dependency_edges": [...]} instead of the plain selection envelope. Keep its original
preference_actions/unresolved_ids schema inside selection.
audit_links has exactly one row per source with source_id, decision_id (same as source_id),
bridge_status (SUPPORTED|CONTRADICTED|UNRESOLVED), brief_basis (one concise auditable
statement), evidence_refs (exact spans), required_support_ids (list), source_relation
(personal_condition|preference|communication|attributed_view|entity_resolution|qualifier|other),
support_eligibility (ALLOW_SUPPORT|BLOCK_SUPPORT|UNKNOWN), direct_drop_reason
(NOT_DIRECTLY_NEEDED|INAPPLICABLE|UNRESOLVED|null). A directly selected item has null drop
reason; a dropped item has a reason. An inapplicable preference must BLOCK_SUPPORT.
NOT_DIRECTLY_NEEDED + ALLOW_SUPPORT is only for structural entity/qualifier evidence,
never a way to revive rejected preferences. Mixed rejected preference and structural
content that cannot be separated using existing legal spans must not be reintroduced.

Dependencies express NECESSARY interpretation of an already selected source, not enriching
the response. Each edge has source_id, target_id, relation, necessary:true, evidence_refs.
Allowed relations: membership, coreference_resolution, qualifier, antecedent,
negation_context, explicit_update_context, jointly_required_condition. Cite both connected
sources; source_id's required_support_ids must match its edge targets. Only supplied memory
IDs are valid targets. Source IDs F0,F1,... refer to fixed_facts for audit only, not targets.
No topical edges or arbitrary assumptions that friends/coworkers all participate. Unknown
eligibility never authorizes a support addition. Cycles cannot create an initial selection.
""" + FIELD


def request(stage, task, model, cap, style_prompt=None, arm=None, memory_view=None, task_view=None):
    """No evaluation metadata, uid, benchmark name or hidden labels enter requests."""
    if stage == "Memory":
        system, payload = MEMORY, memory_payload(task)
    elif stage == "MemorySummary":
        system, payload = SUMMARY, memory_payload(task)
    elif stage == "Task":
        system, payload = TASK, task_payload(task)
    elif stage == "Selector":
        if not isinstance(style_prompt, str) or not style_prompt.strip() or arm not in ARMS:
            raise ValueError("A frozen base selector and named ablation are required")
        system = style_prompt + (ATTR_HINT if arm != "R0" else "") + (TYPED if ARMS[arm]["typed"] else "")
        payload = matching_payload(task, arm, memory_view, task_view)
    else:
        raise ValueError("Unknown generation stage")
    return {"model": model, "messages": [{"role":"system","content":system},
            {"role":"user","content":json.dumps(payload, ensure_ascii=False)}],
            "temperature":0,"max_tokens":cap,"stream":True,"stream_options":{"include_usage":True}}
