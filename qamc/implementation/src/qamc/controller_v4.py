"""Read-side v4 layered on the existing retriever, stores and actor."""
from __future__ import annotations

from .actor import Actor
from .common import ROOT, canonical, token_estimate
from .contracts_v4 import answer_contract, normalize_task, target_time, validate_ledger
from .evidence_compiler import APPLICATIONS, ROLES, source_pack
from .memory_view import actor_view
from .task_resolver import TaskResolver
from .evidence_compiler import EvidenceCompiler


class ResolverV4:
    def __init__(self, gateway):
        self.gateway = gateway
        self.prompt = (ROOT / "prompts/task_resolver_v4.md").read_text()

    def parse(self, query, context, query_time, key):
        def check(obj):
            assert obj.get("task_goal") and isinstance(obj.get("required_slots"), list)
            assert 1 <= len(obj.get("search_queries", [])) <= 4
            assert obj.get("time_mode") in ("current", "historical", "change", "unspecified")
            assert len({s["id"] for s in obj["required_slots"]}) == len(obj["required_slots"])
        raw = self.gateway.object(key + "/resolve", self.prompt,
                                  {"query": query, "current_context": context, "query_time": query_time}, check)
        return normalize_task(raw, query)


class CompilerV4:
    def __init__(self, gateway):
        self.gateway = gateway
        self.prompt = (ROOT / "prompts/evidence_compiler_v4.md").read_text()

    def compile(self, task, candidates, current, sources, key):
        mids = {d["id"] for d in candidates if d["kind"] == "memory"}
        by_source = {s["id"]: s for s in sources}
        ids = {n["id"] for n in task["required_slots"]}

        def check(obj):
            assert isinstance(obj.get("items"), list) and isinstance(obj.get("needs"), list)
            assert {n["id"] for n in obj["needs"]} == ids
            assert len(obj.get("refinement", [])) <= 4
            for item in obj["items"]:
                assert item["need_id"] in ids and item["role"] in ROLES
                assert item["application"] in APPLICATIONS
                assert set(item.get("memory_ids") or []) <= mids
                assert item["source_ids"] and set(item["source_ids"]) <= set(by_source)
                assert item.get("quote") and any(item["quote"] in by_source[s]["content"] for s in item["source_ids"])
            validate_ledger(obj, task, sources)
            for decision in obj["decisions"]:
                for ev in decision.get("evidence") or []:
                    assert any(ev.get("quote", "") and ev["quote"] in by_source[s]["content"]
                               for s in ev["source_ids"]), "decision quote must be verbatim"
        return self.gateway.object(key, self.prompt,
                                   {"task_contract": task, "candidates": candidates,
                                    "source_evidence": sources, "current_evidence": current}, check, 8192)


class ControllerV4:
    def __init__(self, gateway, retriever, *, task_contract=True, decision_binding=True,
                 answer_commitment=True, max_rounds=2):
        self.resolver = ResolverV4(gateway) if task_contract else TaskResolver(gateway)
        self.compiler = CompilerV4(gateway) if decision_binding else EvidenceCompiler(gateway)
        self.actor = Actor(gateway)
        if answer_commitment:
            self.actor.prompt = (ROOT / "prompts/actor_common_v4.md").read_text()
        self.retriever = retriever
        self.max_rounds = max_rounds
        self.switches = {"task_contract": task_contract, "decision_binding": decision_binding,
                         "answer_commitment": answer_commitment}

    def answer(self, case, store, key):
        context = case["history"][-2:]
        task = self.resolver.parse(case["query"], context, case.get("query_time"), key)
        if not self.switches["task_contract"]:
            # Preserve the old Resolver's need list for the task-contract ablation.
            # These slots are deliberately not filtered by a query anchor.
            task = {**task, "required_slots": [
                {"id": n["id"], "description": n["description"], "origin": "LEGACY_RESOLVER",
                 "priority": "REQUIRED", "query_anchor": None} for n in task["information_needs"]],
                    "optional_preferences": []}
        # A typed time target is the only value passed to the state comparator.
        task["target_times"] = [target_time(task)] if target_time(task) else []
        candidates = self.retriever.search(task, store)
        rounds = []
        for iteration in range(self.max_rounds):
            sources = source_pack(store, candidates, 24000)
            query_source = {"id": "CURRENT_QUERY", "role": "user", "content": case["query"]}
            sources = list({s["id"]: s for s in [query_source] + context + sources}.values())
            view = self.compiler.compile(task, candidates, context, sources, key + f"/compile{iteration + 1}")
            rounds.append({"round": iteration + 1, "candidate_ids": [d["id"] for d in candidates],
                           "source_ids": [s["id"] for s in sources], "compiled": view,
                           "candidate_tokens": token_estimate(canonical(candidates)),
                           "source_tokens": token_estimate(canonical(sources))})
            actions = view.get("refinement") or []
            if not actions or iteration + 1 == self.max_rounds:
                break
            queries = [a["query"] for a in actions if a.get("query")]
            new = self.retriever.search(task, store, queries) if queries else []
            new += self.retriever.trace(store, actions)
            old = {d["id"] for d in candidates}
            novel = [d for d in new if d["id"] not in old]
            if not novel:
                rounds[-1]["stop_reason"] = "no_new_evidence"
                break
            candidates = (candidates + novel)[:48]
        final_view = actor_view(view)
        if self.switches["decision_binding"]:
            final_view["decision_ledger"] = view["decisions"]
            if self.switches["answer_commitment"]:
                final_view["answer_contract"] = answer_contract(view, task)
        if self.switches["task_contract"]:
            final_view["task_contract"] = {"required_slots": task["required_slots"],
                                           "optional_preferences": task["optional_preferences"]}
        answer = self.actor.generate(case["query"], context, final_view, key + "/actor", case.get("query_time"))
        return {"answer": answer, "task_needs": task, "retrieval_rounds": rounds,
                "memory_view": final_view, "retrieved_memory_ids": [d["id"] for d in candidates],
                "switches": self.switches}
