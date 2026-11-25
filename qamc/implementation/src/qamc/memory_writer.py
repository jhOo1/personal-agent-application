from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict

from .common import ROOT, canonical, sha, token_estimate
from .influence_graph import InfluenceGraph, PoolManager
from .memory_store import MemoryRecord, compatible_scope


def validate_writer_plan(obj, allowed_sources, prior_records, strict_state_scope=False):
    assert isinstance(obj["records"], list) and len(obj["records"]) <= 40, "at most 40 concise atomic records"
    assert len(obj.get("relations", [])) <= 20, "at most 20 necessary relations"
    assert len(obj.get("summary_fields", [])) <= 6, "at most 6 summary fields"
    local = [r["local_id"] for r in obj["records"]]
    assert len(local) == len(set(local))
    metadata = {r.memory_id: asdict(r) for r in prior_records}
    metadata.update({r["local_id"]: r for r in obj["records"]})
    for record in obj["records"]:
        assert isinstance(record["content"], str) and record["content"] and isinstance(record["source_refs"], list) and record["source_refs"]
        assert set(record["source_refs"]) <= allowed_sources
        assert isinstance(record["subject"], str) and record["subject"]
        assert isinstance(record["attribute"], str) and record["attribute"]
        assert isinstance(record["scope"], dict)
    for edge in obj.get("relations", []):
        assert edge["source_id"] in metadata and edge["target_id"] in metadata
        assert edge["relation"] in ("SUPERSEDES", "CORRECTS", "REVOKES", "SCOPED_OVERRIDE", "SCOPED_EXCEPTION", "REINFORCE", "REINFORCES", "ADD", "EXTENDS", "REFINES", "KEEP_CONFLICT", "SUPPORTS", "RELATED_TO")
        if edge["relation"] in ("SUPERSEDES", "CORRECTS", "REVOKES", "SCOPED_OVERRIDE"):
            source, target = metadata[edge["source_id"]], metadata[edge["target_id"]]
            assert source["subject"].casefold() == target["subject"].casefold(), "state edge crosses subjects"
            assert source["attribute"] == target["attribute"], "state edge must use the same stable property attribute; otherwise preserve distinct records"
            assert compatible_scope(source["scope"], target["scope"]), "state edge crosses incompatible scopes"
            assert source.get("source_kind") != "temporary_exception", "temporary exception cannot supersede persistent memory"
            if strict_state_scope:
                assert edge.get("affected_scope"), "state update needs an explicit nonempty affected scope"
                assert edge.get("evidence_refs"), "state update needs cited change evidence"
    assert len({f["key"] for f in obj.get("summary_fields", [])}) == len(obj.get("summary_fields", []))
    for field in obj.get("summary_fields", []):
        assert field["claim"] and field["support_ids"] and set(field["support_ids"]) <= set(metadata)


def chunks(history, budget=6000):
    """Chronological session groups; question and evaluation fields are never accepted."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    current, size, session = [], 0, None
    for turn in history:
        sid = turn.get("session_id", "history")
        pieces = enc.encode(turn["content"])
        for start in range(0, max(1, len(pieces)), budget - 300):
            part = {**turn, "content": enc.decode(pieces[start:start + budget - 300])}
            cost = token_estimate(canonical(part))
            if current and (size + cost > budget or sid != session):
                yield current
                current, size = [], 0
            current.append(part)
            size += cost
            session = sid
    if current:
        yield current


class MemoryWriter:
    def __init__(self, gateway, retriever):
        self.gateway, self.retriever = gateway, retriever
        self.prompt = (ROOT / "prompts" / "memory_writer.md").read_text()

    def validate_plan(self, obj, allowed_sources, prior_records):
        validate_writer_plan(obj, allowed_sources, prior_records)

    def ingest(self, history, store):
        expected_hash = sha(history)
        prior = store.db.execute("SELECT value FROM meta WHERE key='history_sha'").fetchone()
        if prior and prior[0] != expected_hash:
            raise ValueError("history changed in existing namespace")
        store.db.execute("INSERT OR IGNORE INTO meta VALUES ('history_sha',?)", (expected_hash,))
        store.db.commit()
        original = {t["id"]: t for t in history}
        statuses = []
        for n, segment in enumerate(chunks(history)):
            marker = "chunk:" + str(n)
            done = store.db.execute("SELECT value FROM meta WHERE key=?", (marker,)).fetchone()
            if done:
                statuses.append(done[0])
                continue
            # A resumed history cannot redisclose a source already explicitly erased.
            segment = [turn for turn in segment if not store.is_source_erased(turn['id'])]
            if not segment:
                with store.db:
                    store.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (marker, "erased"))
                statuses.append("erased")
                continue
            # Only current/past sources exist while extracting this segment.
            store.add_sources([original[t["id"]] for t in segment])
            prior_records = store.records()
            if prior_records:
                candidates = self.retriever.search({"goal": "\n".join(t["content"] for t in segment), "time_mode": "unspecified"},
                                                   store, status_aware=False)
                ids = [d["id"] for d in candidates if d["kind"] == "memory"]
                prior_records = [store.get(i) for i in ids][:24]
            payload = {"segment": segment, "existing_memories": [asdict(r) for r in prior_records]}
            allowed_sources = {t["id"] for t in segment}
            existing_ids = {r.memory_id for r in prior_records}

            def validate(obj):
                self.validate_plan(obj, allowed_sources, prior_records)

            key = f"store/{sha(store.namespace)[:16]}/chunk{n:04d}/{sha(segment)[:12]}"
            try:
                obj = self.gateway.object(key + "/writer", self.prompt, payload, validate, 8192)
                mapping = {r["local_id"]: f"M{n:04d}_{j:03d}" for j, r in enumerate(obj["records"])}
                records = []
                for raw in obj["records"]:
                    source_date = next((t.get("recorded_at") for t in segment if t["id"] in raw["source_refs"]), None)
                    records.append(MemoryRecord(memory_id=mapping[raw["local_id"]], content=raw["content"],
                                   semantic_type=raw.get("semantic_type", "fact"), source_kind=raw.get("source_kind", "explicit_user"),
                                   subject=raw["subject"], attribute=raw["attribute"], scope=raw["scope"],
                                   recorded_at=source_date, valid_from=raw.get("valid_from"), valid_to=raw.get("valid_to"),
                                   source_refs=raw["source_refs"]))
                edges = []
                for edge in obj.get("relations", []):
                    relation = "SUPPORTS" if edge["relation"] in ("REINFORCE", "REINFORCES") else edge["relation"]
                    edges.append({**edge, "relation": relation,
                                  "source_id": mapping.get(edge["source_id"], edge["source_id"]),
                                  "target_id": mapping.get(edge["target_id"], edge["target_id"])})
                summary = obj.get("summary_fields", [])
                if summary:
                    sid = f"S{n:04d}"
                    fields = {f["key"]: f["claim"] for f in summary}
                    supports = {f["key"]: [mapping.get(i, i) for i in f["support_ids"]] for f in summary}
                    new_by_id = {r.memory_id: r for r in records}
                    support_records = {mid: new_by_id.get(mid) or store.get(mid) for mid in {x for refs in supports.values() for x in refs}}
                    summary_sources = sorted({ref for r in support_records.values() for ref in r.source_refs})
                    records.append(MemoryRecord(sid, "\n".join(fields.values()), semantic_type="summary", source_kind="inferred",
                                                subject="conversation", attribute="session_summary", source_refs=summary_sources,
                                                fields=fields, field_supports=supports))
                    for mid in sorted({x for refs in supports.values() for x in refs}):
                        edges.append({"source_id": sid, "target_id": mid, "relation": "DERIVED_FROM", "evidence_refs": support_records[mid].source_refs})
                # One transaction commits records, both edge indexes, pools and field invalidation.
                with store.db:
                    changes = InfluenceGraph(store).update(records, edges=edges, transaction=False)
                    PoolManager(store).apply(changes, transaction=False)
                    store.db.execute("INSERT INTO meta VALUES (?,?)", (marker, "ok"))
                statuses.append("ok")
            except Exception as exc:
                if self.gateway.disabled or (self.gateway.root / "STOP").exists():
                    raise
                # Raw sources are deliberately retained as a recoverable evidence layer.
                with store.db:
                    store.log({"event": "writer_failure", "chunk": n, "error": str(exc), "raw_sources_retained": True})
                    store.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (marker, "failed:" + str(exc)))
                statuses.append("failed:" + str(exc))
        # Insert any omitted raw sources (e.g. empty turns) without exposing evaluation metadata.
        store.add_sources(history)
        with store.db:
            store.db.execute("INSERT OR REPLACE INTO meta VALUES ('ingestion_complete','true')")
        return {"chunks": len(statuses), "successful_chunks": statuses.count("ok"), "erased_chunks": statuses.count("erased"),
                "failed_chunks": sum(s not in ("ok", "erased") for s in statuses), "source_count": len(store.sources()),
                "record_count": len(store.records()), "status": "ok" if all(s in ("ok", "erased") for s in statuses) else "partial"}
