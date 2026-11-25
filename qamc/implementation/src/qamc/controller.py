from __future__ import annotations

from .actor import Actor
from .common import canonical, token_estimate
from .evidence_compiler import EvidenceCompiler, source_pack
from .memory_view import actor_view
from .task_resolver import TaskResolver


class Controller:
    def __init__(self, gateway, retriever, max_rounds=2):
        self.resolver = TaskResolver(gateway)
        self.compiler = EvidenceCompiler(gateway)
        self.actor = Actor(gateway)
        self.retriever, self.max_rounds = retriever, max_rounds

    def answer(self, case, store, key):
        context = case["history"][-2:]
        needs = self.resolver.parse(case["query"], context, case.get("query_time"), key)
        if needs["time_mode"] == "current" and not needs.get("target_times") and case.get("query_time"):
            needs["target_times"] = [case["query_time"]]
        candidates = self.retriever.search(needs, store)
        rounds = []
        view = None
        for iteration in range(self.max_rounds):
            sources = source_pack(store, candidates, 24000)
            sources = list({s["id"]: s for s in context + sources}.values())
            view = self.compiler.compile(needs, candidates, context, sources, key + f"/compile{iteration + 1}")
            rounds.append({"round": iteration + 1, "candidate_ids": [x["id"] for x in candidates],
                           "source_ids": [x["id"] for x in sources], "compiled": view,
                           "candidate_tokens": token_estimate(canonical(candidates)),
                           "source_tokens": token_estimate(canonical(sources))})
            actions = view.get("refinement", [])
            if not actions or iteration + 1 == self.max_rounds:
                break
            queries = [a["query"] for a in actions if a.get("query")]
            new = self.retriever.search(needs, store, queries) if queries else []
            new += self.retriever.trace(store, actions)
            old_ids = {d["id"] for d in candidates}
            novel = [d for d in new if d["id"] not in old_ids]
            if not novel:
                rounds[-1]["stop_reason"] = "no_new_evidence"
                break
            combined, budget = [], 0
            for doc in candidates + novel:
                cost = token_estimate(canonical(doc))
                if budget + cost <= 24000 and len(combined) < 48:
                    combined.append(doc)
                    budget += cost
            candidates = combined
        final_view = actor_view(view)
        answer = self.actor.generate(case["query"], context, final_view, key + "/actor", case.get("query_time"))
        return {"answer": answer, "task_needs": needs, "retrieval_rounds": rounds, "memory_view": final_view,
                "retrieved_memory_ids": [d["id"] for d in candidates],
                "active_memory_ids": [d["id"] for d in candidates if d.get("query_state") == "active"],
                "historical_memory_ids": [d["id"] for d in candidates if d.get("query_state") in ("suppressed", "expired")]}
