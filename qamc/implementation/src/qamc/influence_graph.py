from __future__ import annotations

from contextlib import nullcontext

from .common import canonical
from .memory_store import MemoryStore, compatible_scope, covers_scope

RELATIONS = {"SUPERSEDES", "CORRECTS", "REVOKES", "SCOPED_OVERRIDE", "DERIVED_FROM", "SUPPORTS", "RELATED_TO", "SCOPED_EXCEPTION", "KEEP_CONFLICT", "ADD", "EXTENDS", "REFINES"}
STATE_RELATIONS = {"SUPERSEDES", "CORRECTS", "REVOKES", "SCOPED_OVERRIDE"}


class InfluenceGraph:
    def __init__(self, store: MemoryStore):
        self.store = store

    def update(self, new_records, existing_records=None, edges=(), transaction=True):
        """Store one edge and expose both directions; reject unsafe global updates."""
        changes = []
        with (self.store.db if transaction else nullcontext()):
            for record in new_records:
                self.store.put(record)
            for edge in edges:
                source, target = self.store.get(edge["source_id"]), self.store.get(edge["target_id"])
                relation = edge["relation"]
                if not source or not target or source.memory_id == target.memory_id or relation not in RELATIONS:
                    raise ValueError("invalid influence edge")
                scope = edge.get("affected_scope") or source.scope
                if relation in STATE_RELATIONS:
                    if source.subject.casefold() != target.subject.casefold() or source.attribute != target.attribute:
                        raise ValueError("state update crosses subject or attribute")
                    if not compatible_scope(source.scope, target.scope) or not compatible_scope(scope, target.scope):
                        raise ValueError("state update crosses incompatible scope")
                    if source.source_kind == "temporary_exception":
                        raise ValueError("temporary exception cannot supersede persistent state")
                refs = edge.get("evidence_refs") or source.source_refs
                if any(self.store.source(ref) is None for ref in refs):
                    raise ValueError("edge evidence not found")
                effective = edge.get("effective_time") or source.valid_from or source.recorded_at
                self.store.db.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?,?)",
                                      (source.memory_id, target.memory_id, relation, canonical(scope), effective, canonical(refs)))
                changes.append({**edge, "affected_scope": scope, "effective_time": effective})
        return changes


class PoolManager:
    def __init__(self, store: MemoryStore):
        self.store = store

    def apply(self, graph_changes, transaction=True):
        affected = []
        with (self.store.db if transaction else nullcontext()):
            for edge in graph_changes:
                if edge["relation"] not in STATE_RELATIONS:
                    continue
                target = self.store.get(edge["target_id"])
                if covers_scope(edge["affected_scope"], target.scope):
                    target.pool, target.status_reason = "suppressed", edge["relation"].lower()
                    self.store.put(target)
                # Only derived fields depending on the affected record lose current validity.
                queue, visited = [target.memory_id], set()
                while queue:
                    old = queue.pop(0)
                    if old in visited:
                        continue
                    visited.add(old)
                    for e in self.store.influenced_by(old):
                        if e["relation"] != "DERIVED_FROM":
                            continue
                        derived = self.store.get(e["source_id"])
                        fields = [f for f, refs in derived.field_supports.items() if old in refs]
                        if not fields and not derived.field_supports:
                            derived.pool, derived.status_reason = "suppressed", "source_changed_requires_regeneration"
                        for f in fields:
                            if f not in derived.stale_fields:
                                derived.stale_fields.append(f)
                        if fields:
                            derived.status_reason = "partial_source_change"
                        self.store.put(derived)
                        affected.append({"memory_id": derived.memory_id, "fields": fields, "cause": old})
                        queue.append(derived.memory_id)
            self.store.log({"event": "pool_and_dependency_update", "changes": graph_changes, "derived_affected": affected})
        return affected

    def state(self, record, target_time=None, scope=None):
        """Query-local as-of read; historical access never changes the stored pool."""
        state = "active"
        if target_time and record.valid_from and target_time < record.valid_from:
            return "not_yet_valid"
        if target_time and record.valid_to and target_time > record.valid_to:
            return "expired"
        for edge in self.store.influenced_by(record.memory_id):
            if edge["relation"] not in STATE_RELATIONS:
                continue
            if target_time and edge["effective_time"] and target_time < edge["effective_time"]:
                continue
            if scope is not None and not compatible_scope(edge["affected_scope"], scope):
                continue
            if covers_scope(edge["affected_scope"], scope if scope is not None else record.scope):
                state = "suppressed"
            else:
                state = "partially_suppressed"
        if record.status_reason == "source_changed_requires_regeneration":
            state = "source_changed_requires_regeneration"
        return state
