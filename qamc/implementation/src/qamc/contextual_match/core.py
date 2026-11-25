"""Pure public-input boundaries and deterministic dependency compilation.

All semantic attributes and edges remain model predictions. Validation proves
source identity and execution contracts, never that a predicted use is correct.
No model client, filesystem, Store, reference labels, or scorer is imported here.
"""
from copy import deepcopy
from qamc.common import sha
from qamc.pa.core import compile_view

SCHEMA = "contextual_match_v1"
RELATIONS = {"membership", "coreference_resolution", "qualifier", "antecedent",
             "negation_context", "explicit_update_context", "jointly_required_condition"}
ARMS = {
    "R0": {"memory": None, "task": False, "typed": False, "closure": False},
    "R1": {"memory": "summary", "task": False, "typed": False, "closure": False},
    "R2": {"memory": "attributes", "task": False, "typed": False, "closure": False},
    "R3": {"memory": "attributes", "task": True, "typed": False, "closure": False},
    "R4": {"memory": "attributes", "task": True, "typed": True, "closure": False},
    "R5": {"memory": "attributes", "task": True, "typed": True, "closure": True},
}


class ContractError(ValueError):
    """A structural error, not a benchmark semantic failure."""


def exact_keys(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ContractError("Unexpected or missing schema fields")


def memory_payload(task):
    # No uid/query/current_context/facts: relations may use this snapshot only.
    return {"schema": SCHEMA, "sources": [dict(row, source_sha256=sha(row["text"]))
            for row in deepcopy(task.payload()["memories"])]}


def task_payload(task):
    # Historical fixed facts are deliberately absent from query-only encoding.
    return {"schema": SCHEMA, "query": task.query, "current_context": task.current_context}


def source_map(task, phase):
    if phase == "memory":
        return {m.memory_id: m.text for m in task.memories}
    if phase == "task":
        return {"query": task.query, "current_context": task.current_context}
    if phase != "match":
        raise ContractError("Unknown source boundary")
    return {**source_map(task, "memory"), **source_map(task, "task"),
            **{f"F{i}": text for i, text in enumerate(task.fixed_facts)}}


def validate_ref(ref, sources):
    exact_keys(ref, {"source_id", "start", "end", "quote"})
    sid, start, end = ref["source_id"], ref["start"], ref["end"]
    if not isinstance(sid, str) or sid not in sources:
        raise ContractError("Unknown evidence source")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(sources[sid]):
        raise ContractError("Evidence offset out of bounds")
    if not isinstance(ref["quote"], str) or sources[sid][start:end] != ref["quote"]:
        raise ContractError("Evidence quote mismatch")


def validate_field(field, sources, task_side=False):
    exact_keys(field, {"value", "status", "evidence"})
    statuses = {"EXPLICIT", "INFERRED", "UNKNOWN"} | ({"TASK_IMPLIED"} if task_side else set())
    if field["status"] not in statuses or not isinstance(field["evidence"], list):
        raise ContractError("Invalid attributed field")
    if field["status"] == "UNKNOWN":
        if field["value"] is not None or field["evidence"]:
            raise ContractError("UNKNOWN must not invent a value or source")
    elif field["value"] is None or not field["evidence"]:
        raise ContractError("A supported attribute requires evidence")
    for ref in field["evidence"]:
        validate_ref(ref, sources)


def validate_memory_view(task, view):
    exact_keys(view, {"schema", "sources"})
    if view["schema"] != SCHEMA or not isinstance(view["sources"], list):
        raise ContractError("Wrong MemoryView schema")
    originals = source_map(task, "memory")
    seen = set()
    for row in view["sources"]:
        exact_keys(row, {"source_id", "source_sha256", "subject", "content_kind", "properties",
                         "observed_context", "explicit_scope", "relations"})
        sid = row["source_id"]
        if sid not in originals or sid in seen or row["source_sha256"] != sha(originals[sid]):
            raise ContractError("Memory identity/hash mismatch")
        seen.add(sid)
        for key in ("subject", "content_kind"):
            validate_field(row[key], originals)
        for key in ("properties", "observed_context", "explicit_scope", "relations"):
            if not isinstance(row[key], list):
                raise ContractError("Attribute collection must be a list")
            for field in row[key]:
                validate_field(field, originals)
    if seen != originals.keys():
        raise ContractError("MemoryView must cover the whole allowed snapshot")
    return deepcopy(view)


def validate_task_view(task, view):
    exact_keys(view, {"schema", "deliverables", "roles", "constraints", "unresolved_mentions"})
    if view["schema"] != SCHEMA:
        raise ContractError("Wrong TaskView schema")
    for key in ("deliverables", "roles", "constraints", "unresolved_mentions"):
        if not isinstance(view[key], list):
            raise ContractError("TaskView collection must be a list")
        for field in view[key]:
            validate_field(field, source_map(task, "task"), True)
    return deepcopy(view)


def cache_key(task, phase, prompt, model_config):
    # Full allowed history is necessary for cross-source entity relations.
    payload = memory_payload(task) if phase == "memory" else task_payload(task) if phase == "task" else None
    if payload is None:
        raise ContractError("Only isolated encoders have representation cache keys")
    return sha({"schema": SCHEMA, "normalization": "exact_unicode_v1", "phase": phase,
                "payload": payload, "prompt": prompt, "model_service_config": model_config})


def matching_payload(task, arm, memory_view=None, task_view=None):
    if arm not in ARMS:
        raise ContractError("Unknown ablation")
    config = ARMS[arm]
    payload = task.payload()
    if config["memory"] == "attributes":
        payload["memory_view"] = validate_memory_view(task, memory_view)
    elif config["memory"] == "summary":
        exact_keys(memory_view, {"summary"})
        if not isinstance(memory_view["summary"], str) or not memory_view["summary"].strip():
            raise ContractError("Empty equal-budget memory summary")
        payload["memory_summary"] = memory_view["summary"]
    elif memory_view is not None:
        raise ContractError("Ablation unexpectedly receives historical metadata")
    if config["task"]:
        payload["task_view"] = validate_task_view(task, task_view)
    elif task_view is not None:
        raise ContractError("Ablation unexpectedly receives task metadata")
    return payload


def normalize_selection(task, selection):
    """Translate the frozen sparse Style codec into its original compiler form."""
    exact_keys(selection, {"preference_actions", "unresolved_ids"})
    memories = {m.memory_id: m for m in task.memories}
    if not isinstance(selection["preference_actions"], list):
        raise ContractError("Actions must be a list")
    rows = []
    for row in selection["preference_actions"]:
        if not isinstance(row, dict) or row.get("memory_id") not in memories:
            raise ContractError("Unknown action source")
        decision = row.get("decision")
        exact_keys(row, {"memory_id", "decision", "keep_span_ids"} if decision == "PARTIAL"
                   else {"memory_id", "decision"})
        spans = list(memories[row["memory_id"]].spans())
        rows.append({**row, "keep_span_ids": row["keep_span_ids"] if decision == "PARTIAL"
                     else spans if decision == "APPLY" else []})
    normalized = {**selection, "preference_actions": rows}
    try:
        compile_view(task, normalized, "V1")
    except (ValueError, TypeError, KeyError) as exc:
        raise ContractError(str(exc)) from exc
    return normalized


def validate_match(task, result):
    exact_keys(result, {"selection", "audit_links", "dependency_edges"})
    normalize_selection(task, result["selection"])
    if not isinstance(result["audit_links"], list) or not isinstance(result["dependency_edges"], list):
        raise ContractError("Match sidecars must be lists")
    ids = {m.memory_id for m in task.memories}
    links = {}
    actions = {a["memory_id"]: a for a in result["selection"]["preference_actions"]}
    for row in result["audit_links"]:
        exact_keys(row, {"source_id", "decision_id", "bridge_status", "brief_basis", "evidence_refs",
                         "required_support_ids", "source_relation", "support_eligibility", "direct_drop_reason"})
        sid = row["source_id"]
        if sid not in ids or sid in links or row["decision_id"] != sid:
            raise ContractError("Ambiguous audit identity")
        if row["bridge_status"] not in {"SUPPORTED", "CONTRADICTED", "UNRESOLVED"}:
            raise ContractError("Unknown bridge status")
        if row["support_eligibility"] not in {"ALLOW_SUPPORT", "BLOCK_SUPPORT", "UNKNOWN"}:
            raise ContractError("Unknown support eligibility")
        if row["source_relation"] not in {"personal_condition", "preference", "communication",
                                           "attributed_view", "entity_resolution", "qualifier", "other"}:
            raise ContractError("Unknown source relation")
        drop = row["direct_drop_reason"]
        if drop not in {None, "NOT_DIRECTLY_NEEDED", "INAPPLICABLE", "UNRESOLVED"}:
            raise ContractError("Unknown drop reason")
        is_drop = actions[sid]["decision"] == "DROP"
        if is_drop != (drop is not None):
            raise ContractError("Drop status contradicts the direct selection")
        if drop == "INAPPLICABLE" and row["support_eligibility"] == "ALLOW_SUPPORT":
            raise ContractError("Rejected preference cannot be revived as support")
        if not isinstance(row["brief_basis"], str) or not row["brief_basis"].strip():
            raise ContractError("Missing compact auditable basis")
        if not isinstance(row["evidence_refs"], list) or not row["evidence_refs"]:
            raise ContractError("Audit link lacks source support")
        for ref in row["evidence_refs"]:
            validate_ref(ref, source_map(task, "match"))
        support = row["required_support_ids"]
        if not isinstance(support, list) or len(set(support)) != len(support) or not set(support) <= ids:
            raise ContractError("Invalid required support IDs")
        links[sid] = row
    if set(links) != ids:
        raise ContractError("Audit links must cover every candidate")
    seen_edges = set()
    for edge in result["dependency_edges"]:
        exact_keys(edge, {"source_id", "target_id", "relation", "necessary", "evidence_refs"})
        a, b = edge["source_id"], edge["target_id"]
        if a not in ids or b not in ids or a == b or (a, b) in seen_edges:
            raise ContractError("Invalid dependency identity")
        seen_edges.add((a, b))
        if edge["relation"] not in RELATIONS or edge["necessary"] is not True:
            raise ContractError("Unsupported dependency relation")
        if b not in links[a]["required_support_ids"]:
            raise ContractError("Edge not declared by its source decision")
        if not isinstance(edge["evidence_refs"], list) or not edge["evidence_refs"]:
            raise ContractError("Dependency lacks evidence")
        for ref in edge["evidence_refs"]:
            validate_ref(ref, source_map(task, "match"))
        cited = {r["source_id"] for r in edge["evidence_refs"]}
        if not {a, b} <= cited:
            raise ContractError("Dependency must cite both connected sources")
    declared = {(sid, target) for sid, link in links.items() for target in link["required_support_ids"]}
    if declared != seen_edges:
        raise ContractError("Declared dependencies and edge list differ")
    return deepcopy(result)


def compile_match(task, result, closure=False):
    """Run either execution ablation on exactly the same matcher prediction."""
    validate_match(task, result)
    selection = normalize_selection(task, result["selection"])
    actions = {a["memory_id"]: a for a in selection["preference_actions"]}
    links = {a["source_id"]: a for a in result["audit_links"]}
    memories = {m.memory_id: m for m in task.memories}
    seeds = {sid for sid, action in actions.items() if action["decision"] != "DROP"}
    selected, paths, already_in_f = set(seeds), {sid: [sid] for sid in seeds}, []
    queue = list(sorted(seeds)) if closure else []
    while queue:
        sid = queue.pop(0)
        for edge in result["dependency_edges"]:
            if edge["source_id"] != sid:
                continue
            target = edge["target_id"]
            if target in selected:
                continue
            link = links[target]
            if (link["support_eligibility"] != "ALLOW_SUPPORT"
                    or link["direct_drop_reason"] != "NOT_DIRECTLY_NEEDED"
                    or link["source_relation"] not in {"entity_resolution", "qualifier"}):
                raise ContractError("Dependency target is not eligible structural support")
            if memories[target].text in task.fixed_facts:
                already_in_f.append(target)
                continue
            selected.add(target)
            paths[target] = paths[sid] + [target]
            queue.append(target)
    for sid in selected - seeds:
        actions[sid] = {"memory_id": sid, "decision": "APPLY", "keep_span_ids": list(memories[sid].spans())}
    final = {"preference_actions": [actions[m.memory_id] for m in task.memories],
             "unresolved_ids": selection["unresolved_ids"]}
    try:
        view = compile_view(task, final, "V1")
    except (ValueError, TypeError, KeyError) as exc:
        raise ContractError(str(exc)) from exc
    # Identical source text is one evidence item, never multiple independent votes.
    seen = set(task.fixed_facts)
    deduped = []
    for item in view["source_evidence"]:
        if item["text"] not in seen:
            seen.add(item["text"])
            deduped.append(item)
    view["source_evidence"] = deduped
    return {"view": view, "selection": final, "audit": {
        "direct_ids": sorted(seeds), "added_by_dependency": sorted(selected - seeds),
        "paths": paths, "already_in_f": sorted(set(already_in_f)),
        "matcher_sha256": sha(result), "closure_enabled": closure,
        "semantic_correctness_guaranteed": False}}
