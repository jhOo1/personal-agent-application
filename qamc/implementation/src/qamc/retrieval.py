from __future__ import annotations

import json
import threading
from dataclasses import asdict

import numpy as np
from rank_bm25 import BM25Okapi

from .common import ROOT, sha, token_estimate, tokens
from .influence_graph import PoolManager


class DenseModels:
    def __init__(self):
        from sentence_transformers import CrossEncoder, SentenceTransformer
        import torch
        conf = json.loads((ROOT / "configs" / "retrieval_models.json").read_text())
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.encoder = SentenceTransformer(conf[0]["local_path"], device=self.device, local_files_only=True)
        self.reranker = CrossEncoder(conf[1]["local_path"], device=self.device, local_files_only=True)
        self.lock = threading.RLock()
        self.cache = ROOT / "runs" / "embedding_cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.model_sha = conf[0]["revision"]

    def encode(self, texts):
        paths = [self.cache / (sha([self.model_sha, t]) + ".npy") for t in texts]
        missing = [(i, t) for i, (t, p) in enumerate(zip(texts, paths)) if not p.exists()]
        with self.lock:
            if missing:
                vecs = self.encoder.encode([t for _, t in missing], batch_size=32, normalize_embeddings=True,
                                           show_progress_bar=False, convert_to_numpy=True)
                for (i, _), v in zip(missing, vecs):
                    # Shared embedding cache stores representations, never cross-namespace candidate IDs.
                    temp = paths[i].with_suffix(".tmp.npy")
                    np.save(temp, v)
                    temp.replace(paths[i])
        return np.stack([np.load(p) for p in paths])

    def rerank(self, query, texts):
        with self.lock:
            return np.asarray(self.reranker.predict([(query, t) for t in texts], batch_size=32,
                                                   show_progress_bar=False)).reshape(-1)


def documents(store):
    docs = []
    for record in store.records():
        data = asdict(record)
        if record.fields:
            content = "\n".join(v for k, v in record.fields.items() if k not in record.stale_fields)
        elif record.status_reason == "source_changed_requires_regeneration":
            continue
        else:
            content = record.content
        if content:
            docs.append({"id": record.memory_id, "kind": "memory", "text": content, "source_ids": record.source_refs,
                         "metadata": {k: data[k] for k in ("subject", "attribute", "scope", "semantic_type", "source_kind", "recorded_at", "valid_from", "valid_to", "pool", "status_reason")}})
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    for turn in store.sources():
        encoded = enc.encode(turn["content"])
        for n, start in enumerate(range(0, max(1, len(encoded)), 320)):
            text = enc.decode(encoded[start:start + 384])
            docs.append({"id": f"raw:{turn['id']}:{n}", "kind": "source", "text": text,
                         "source_ids": [turn["id"]], "metadata": {k: turn[k] for k in
                         ("speaker", "role", "session_id", "recorded_at") if k in turn}})
    return docs


class Retriever:
    def __init__(self, models: DenseModels, top_k=24, token_budget=12000):
        self.models, self.top_k, self.token_budget = models, top_k, token_budget

    def search(self, task_needs, memory_store, queries=None, status_aware=True):
        docs = documents(memory_store)
        if not docs:
            return []
        qs = queries or task_needs.get("search_queries") or [task_needs["goal"]]
        qs = list(dict.fromkeys(q for q in qs if q.strip()))[:4]
        texts = [d["text"] for d in docs]
        vectors = self.models.encode(texts)
        qvecs = self.models.encode(["Represent this sentence for searching relevant passages: " + q for q in qs])
        bm25 = BM25Okapi([tokens(t) or ["empty"] for t in texts])
        fusion = np.zeros(len(docs))
        for q, v in zip(qs, qvecs):
            for scores in (vectors @ v, bm25.get_scores(tokens(q))):
                for rank, idx in enumerate(np.argsort(-scores)[:80]):
                    fusion[idx] += 1 / (60 + rank + 1)
        indexes = list(np.argsort(-fusion)[:64])
        by_id = {d["id"]: i for i, d in enumerate(docs)}
        # Expand actual version/dependency relationships without traversing the whole store.
        for idx in list(indexes[:16]):
            if docs[idx]["kind"] != "memory":
                continue
            for edge in memory_store.neighbors(docs[idx]["id"]):
                for mid in (edge["source_id"], edge["target_id"]):
                    if mid in by_id and by_id[mid] not in indexes:
                        indexes.append(by_id[mid])
        indexes = indexes[:96]
        scores = self.models.rerank(task_needs.get("goal") or qs[0], [texts[i] for i in indexes])
        pool = PoolManager(memory_store)
        ranked = []
        for i, score in zip(indexes, scores):
            doc = dict(docs[i])
            if doc["kind"] == "memory":
                record = memory_store.get(doc["id"])
                doc["query_state"] = pool.state(record, (task_needs.get("target_times") or [None])[0], task_needs.get("scope") or None)
                doc["relations"] = memory_store.neighbors(record.memory_id)
                if status_aware and task_needs.get("time_mode") == "current" and doc["query_state"] in ("suppressed", "expired", "not_yet_valid"):
                    score -= 1.5
            doc["retrieval_score"] = float(score)
            ranked.append(doc)
        ranked.sort(key=lambda d: (-d["retrieval_score"], d["id"]))
        selected, total = [], 0
        for doc in ranked:
            cost = token_estimate(json.dumps(doc, ensure_ascii=False))
            if total + cost > self.token_budget:
                continue
            selected.append(doc)
            total += cost
            if len(selected) >= self.top_k:
                break
        return selected

    def trace(self, store, actions):
        result, seen = [], set()
        for action in actions[:4]:
            ids = list(action.get("ids") or [])
            if action.get("action") == "RESOLVE_VERSION":
                for mid in list(ids):
                    for e in store.neighbors(mid):
                        ids.extend([e["source_id"], e["target_id"]])
            for item in ids:
                record = store.get(item)
                refs = record.source_refs if record else [item]
                for ref in refs:
                    source = store.source(ref)
                    if source and ref not in seen:
                        seen.add(ref)
                        result.append({"id": "trace:" + ref, "kind": "source", "text": source["content"],
                                       "source_ids": [ref], "metadata": {k: source[k] for k in
                                       ("speaker", "role", "recorded_at", "session_id") if k in source}})
        return result
