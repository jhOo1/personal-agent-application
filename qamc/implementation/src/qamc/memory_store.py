"""Transactional source-preserving store with namespace-isolated memories and edges."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .common import canonical, sha


@dataclass
class MemoryRecord:
    memory_id: str
    content: str
    semantic_type: str = "fact"
    source_kind: str = "explicit_user"
    subject: str = "user"
    attribute: str = ""
    scope: dict = field(default_factory=dict)
    recorded_at: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    source_refs: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    field_supports: dict[str, list[str]] = field(default_factory=dict)
    stale_fields: list[str] = field(default_factory=list)
    pool: str = "active"
    status_reason: str = "current"


def compatible_scope(a: dict, b: dict) -> bool:
    """An unspecified key is broad; conflicting explicit subjects/scopes coexist."""
    return all(not (a.get(k) and b.get(k) and a[k] != b[k]) for k in set(a) | set(b))


def covers_scope(a: dict, b: dict) -> bool:
    """Whether a covers every case described by b (empty a is unrestricted)."""
    return all(k in b and b[k] == v for k, v in a.items() if v not in (None, "", "*"))


class MemoryStore:
    def __init__(self, path: Path, namespace: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.namespace = path, namespace
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,ordinal INTEGER,data TEXT);
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,data TEXT);
        CREATE TABLE IF NOT EXISTS edges(source_id TEXT,target_id TEXT,relation TEXT,scope TEXT,effective_time TEXT,evidence TEXT,
          PRIMARY KEY(source_id,target_id,relation,scope));
        CREATE INDEX IF NOT EXISTS edge_forward ON edges(source_id);
        CREATE INDEX IF NOT EXISTS edge_reverse ON edges(target_id);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,data TEXT);
        CREATE TABLE IF NOT EXISTS erasures(source_id TEXT PRIMARY KEY,content_sha TEXT,erased_at TEXT);
        """)
        old = self.db.execute("SELECT value FROM meta WHERE key='namespace'").fetchone()
        if old and old[0] != namespace:
            raise ValueError("namespace mismatch")
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('namespace',?)", (namespace,))
        self.db.commit()

    def add_sources(self, history: list[dict]):
        with self.db:
            base = self.db.execute("SELECT COALESCE(MAX(ordinal),-1)+1 FROM sources").fetchone()[0]
            added = 0
            for n, turn in enumerate(history):
                assert set(turn) <= {"id", "role", "content", "speaker", "recorded_at", "session_id"}
                if self.is_source_erased(turn["id"]):
                    continue
                prior = self.db.execute("SELECT data FROM sources WHERE id=?", (turn["id"],)).fetchone()
                if prior and prior[0] != canonical(turn):
                    raise ValueError("source changed on resume")
                if not prior:
                    self.db.execute("INSERT INTO sources VALUES (?,?,?)", (turn["id"], base + added, canonical(turn)))
                    added += 1

    def sources(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT data FROM sources ORDER BY ordinal")]

    def source(self, source_id: str):
        row = self.db.execute("SELECT data FROM sources WHERE id=?", (source_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def records(self):
        return [MemoryRecord(**json.loads(r[0])) for r in self.db.execute("SELECT data FROM records ORDER BY id")]

    def get(self, memory_id: str):
        row = self.db.execute("SELECT data FROM records WHERE id=?", (memory_id,)).fetchone()
        return MemoryRecord(**json.loads(row[0])) if row else None

    def put(self, record: MemoryRecord):
        if not record.content.strip() or not record.source_refs:
            raise ValueError("memory requires content and provenance")
        if any(self.source(ref) is None for ref in record.source_refs):
            raise ValueError("unknown source reference")
        self.db.execute("INSERT OR REPLACE INTO records VALUES (?,?)", (record.memory_id, canonical(asdict(record))))

    def neighbors(self, memory_id: str):
        return [{"source_id": r[0], "target_id": r[1], "relation": r[2], "affected_scope": json.loads(r[3]),
                 "effective_time": r[4], "evidence_refs": json.loads(r[5])}
                for r in self.db.execute("SELECT * FROM edges WHERE source_id=? OR target_id=?", (memory_id, memory_id))]

    def influences(self, memory_id):
        return [e for e in self.neighbors(memory_id) if e["source_id"] == memory_id]

    def influenced_by(self, memory_id):
        return [e for e in self.neighbors(memory_id) if e["target_id"] == memory_id]

    def log(self, event: dict):
        self.db.execute("INSERT INTO events(data) VALUES (?)", (canonical(event),))

    def is_source_erased(self, source_id: str) -> bool:
        return bool(self.db.execute("SELECT 1 FROM erasures WHERE source_id=?", (source_id,)).fetchone())

    def delete(self, memory_id: str, delete_sources: bool = True):
        """Erase a selected memory and sources, retaining only non-content tombstones.

        Derived fields depending on a changed parent are removed transitively.
        Unrelated supported fields remain when their own sources remain available.
        The immutable external caller history is not treated as storage: subsequent
        ingestion must honor the tombstones rather than reinsert erased turns.
        """
        from datetime import datetime, timezone
        record = self.get(memory_id)
        if not record:
            return
        erased_refs = set(record.source_refs) if delete_sources else set()
        with self.db:
            for ref in erased_refs:
                source = self.source(ref)
                self.db.execute("INSERT OR IGNORE INTO erasures VALUES (?,?,?)",
                                (ref, sha(source) if source else None, datetime.now(timezone.utc).isoformat()))
            pending, queued = [memory_id], {memory_id}
            # A source erased on request cannot continue to support another record.
            for other in self.records():
                if not (set(other.source_refs) & erased_refs):
                    continue
                remaining = [ref for ref in other.source_refs if ref not in erased_refs]
                if not remaining and other.memory_id not in queued:
                    pending.append(other.memory_id)
                    queued.add(other.memory_id)
            deleted, changed, visited = set(), set(), set()
            while pending:
                target = pending.pop(0)
                if target in visited:
                    continue
                visited.add(target)
                for other in self.records():
                    if other.memory_id == target or other.memory_id in deleted:
                        continue
                    fields = [key for key, refs in other.field_supports.items() if target in refs]
                    derivation = any(e['relation'] == 'DERIVED_FROM' and e['target_id'] == target
                                     for e in self.influences(other.memory_id))
                    if not fields and not (derivation and not other.field_supports):
                        continue
                    if fields:
                        for key in fields:
                            other.fields.pop(key, None)
                            other.field_supports.pop(key, None)
                        remaining_supports = {mid for refs in other.field_supports.values() for mid in refs}
                        if target not in remaining_supports:
                            self.db.execute("DELETE FROM edges WHERE source_id=? AND target_id=? AND relation='DERIVED_FROM'",
                                            (other.memory_id, target))
                        other.stale_fields = [key for key in other.stale_fields if key in other.fields]
                        other.content = '\n'.join(other.fields.values())
                    else:
                        other.content = ''
                    if other.content:
                        live_supports = {mid for refs in other.field_supports.values() for mid in refs}
                        refs = {ref for mid in live_supports for support in [self.get(mid)]
                                if support and mid not in deleted for ref in support.source_refs}
                        other.source_refs = sorted(refs - erased_refs)
                        if other.source_refs:
                            self.put(other)
                            changed.add(other.memory_id)
                        else:
                            other.content = ''
                    if other.memory_id not in queued:
                        pending.append(other.memory_id)
                        queued.add(other.memory_id)
                    if not other.content:
                        deleted.add(other.memory_id)
                        self.db.execute("DELETE FROM records WHERE id=?", (other.memory_id,))
                        self.db.execute("DELETE FROM edges WHERE source_id=? OR target_id=?", (other.memory_id, other.memory_id))
                # A partially changed record is propagated, but its remaining fields survive.
                if target == memory_id or target in deleted or target not in changed:
                    deleted.add(target)
                    self.db.execute("DELETE FROM records WHERE id=?", (target,))
                    self.db.execute("DELETE FROM edges WHERE source_id=? OR target_id=?", (target, target))
            for other in self.records():
                if set(other.source_refs) & erased_refs:
                    other.source_refs = [ref for ref in other.source_refs if ref not in erased_refs]
                    if other.source_refs:
                        self.put(other)
            # Remove erased evidence from surviving edges as well as raw sources.
            for source_id, target_id, relation, scope, evidence in self.db.execute(
                    "SELECT source_id,target_id,relation,scope,evidence FROM edges").fetchall():
                refs = [ref for ref in json.loads(evidence) if ref not in erased_refs]
                if not refs:
                    self.db.execute("DELETE FROM edges WHERE source_id=? AND target_id=? AND relation=? AND scope=?",
                                    (source_id, target_id, relation, scope))
                else:
                    self.db.execute("UPDATE edges SET evidence=? WHERE source_id=? AND target_id=? AND relation=? AND scope=?",
                                    (canonical(refs), source_id, target_id, relation, scope))
            for ref in erased_refs:
                self.db.execute("DELETE FROM sources WHERE id=?", (ref,))
            self.log({"event": "actual_delete", "memory_id": memory_id, "source_erasure": delete_sources,
                      "deleted_record_ids": sorted(deleted), "changed_record_ids": sorted(changed)})

    def close(self):
        self.db.close()
