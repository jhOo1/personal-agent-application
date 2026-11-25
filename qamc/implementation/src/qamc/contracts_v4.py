"""Query-grounded, auditable contracts for the v4 read path.

These checks enforce type-level consequences; they do not certify that a
natural-language quotation entails a claim.
"""
from __future__ import annotations

import re

STRENGTH = {"DIRECT", "SUPPORTED_INFERENCE", "PARTIAL", "UNSUPPORTED"}
EVENT = {"CURRENT", "HISTORICAL", "PLANNED", "INTENDED", "COMPLETED", "CANCELLED", "UNKNOWN"}
COMPLETENESS = {"EXHAUSTIVE", "OPEN_WORLD", "UNKNOWN"}
ANSWER_TYPES = {"SHORT_FACT", "COUNT", "TEMPORAL_COMPARISON", "RECOMMENDATION", "EXPLANATION", "UNANSWERABLE"}
EFFECTS = {"parameter", "tie_breaking", "recommendation_reason", "historical_fact", "none"}


def normalize_task(task: dict, query: str) -> dict:
    """Keep old retrieval fields while forbidding unanchored required slots."""
    task = dict(task)
    slots = task.get("required_slots") or task.get("information_needs") or []
    required, optional = [], list(task.get("optional_preferences") or [])
    for slot in slots:
        slot = dict(slot)
        origin = slot.get("origin", "CURRENT_QUERY")
        anchor = str(slot.get("query_anchor") or "").strip()
        if origin != "CURRENT_QUERY" or (anchor and anchor.casefold() not in query.casefold()):
            optional.append({"id": slot["id"], "description": slot["description"],
                             "origin": "HISTORICAL_MEMORY", "priority": "OPTIONAL",
                             "allowed_effect": "COMPATIBLE_PERSONALIZATION"})
            continue
        if not anchor:
            # No anchor is a recoverable contract error, never an extra hard need.
            optional.append({"id": slot["id"], "description": slot["description"],
                             "origin": "UNANCHORED", "priority": "OPTIONAL",
                             "allowed_effect": "COMPATIBLE_PERSONALIZATION"})
            continue
        slot.update(origin="CURRENT_QUERY", priority="REQUIRED", query_anchor=anchor)
        required.append(slot)
    if not required:
        required = [{"id": "need_query", "description": query, "origin": "CURRENT_QUERY",
                     "priority": "REQUIRED", "query_anchor": query}]
    task["required_slots"] = required
    task["optional_preferences"] = optional
    task["information_needs"] = [{"id": x["id"], "description": x["description"]} for x in required]
    task["goal"] = task.get("task_goal") or task.get("goal") or query
    return task


def target_time(task: dict) -> str | None:
    """Return an ISO comparison instant only; ALL_HISTORY is not a date."""
    spec = task.get("temporal_target") or {}
    if isinstance(spec, dict):
        mode = spec.get("mode")
        if mode in {"ALL_HISTORY", "HISTORICAL_RANGE"}:
            return None
        if mode == "AS_OF" and re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:+.Z-]+)?", str(spec.get("date") or "")):
            return spec["date"]
    raw = (task.get("target_times") or [None])[0]
    return raw if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:+.Z-]+)?", raw) else None


def validate_ledger(view: dict, task: dict, sources: list[dict]) -> None:
    ids = {n["id"] for n in task["required_slots"]}
    source_ids = {s["id"] for s in sources}
    decisions = view.get("decisions")
    assert isinstance(decisions, list) and {d["need_id"] for d in decisions} == ids
    for decision in decisions:
        assert decision["answer_type"] in ANSWER_TYPES
        evidence = decision.get("evidence") or []
        for item in evidence:
            assert item["support_type"] in STRENGTH
            assert item["event_state"] in EVENT
            assert set(item.get("source_ids") or []) <= source_ids
            assert item.get("source_ids"), "decision evidence needs a source"
        comp = decision.get("completeness") or {}
        assert comp.get("mode") in COMPLETENESS
        d = decision["decision"]
        assert type(d.get("answerable")) is bool
        if d["answerable"]:
            assert d.get("value") not in (None, ""), "answerable decision needs value"
            assert evidence, "answerable decision needs evidence"
            assert any(e["support_type"] in {"DIRECT", "SUPPORTED_INFERENCE"} for e in evidence)
        if decision["answer_type"] == "COUNT":
            count = decision.get("count") or {}
            assert type(count.get("known_count")) is int and count["known_count"] >= 0
            value = d["value"]
            is_zero = value == 0 or (isinstance(value, str) and bool(re.match(r"^\s*0(?:\b|$)", value)))
            if d["answerable"] and is_zero:
                assert comp["mode"] == "EXHAUSTIVE" or count.get("explicit_total") == 0, "open-world zero is unknown"
            if d["answerable"]:
                assert count.get("explicit_total") is not None or comp["mode"] == "EXHAUSTIVE" or not is_zero
        if decision["answer_type"] != "EXPLANATION" and d["answerable"]:
            assert not (evidence and all(e["event_state"] in {"PLANNED", "INTENDED"} for e in evidence)
                        and decision.get("target_event_state") == "COMPLETED"), "planned is not completed"
    decision_ids = {d["decision_id"] for d in decisions}
    for item in view.get("items") or []:
        assert set(item.get("allowed_decision_ids") or []) <= decision_ids
        if item.get("application") == "PARTIAL_APPLY":
            assert item.get("allowed_decision_ids") and item.get("allowed_effect") in EFFECTS


def answer_contract(view: dict, task: dict) -> dict:
    decisions = view["decisions"]
    return {"task_goal": task["goal"], "required_slots": task["required_slots"],
            "optional_preferences": task["optional_preferences"],
            "decisions": [{"decision_id": d["decision_id"], "need_id": d["need_id"],
                           "answer_type": d["answer_type"], **d["decision"]} for d in decisions],
            "output_rule": "Answer the user directly. Start with the primary value or concrete recommendation. "
                           "Keep short facts concise. State unknown totals as unknown, even when no positive record was retrieved. "
                           "Use only optional preferences compatible with the current query."}
