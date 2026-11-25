from __future__ import annotations

import argparse
import collections
import json
import random
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait

from .actor import Actor
from .api import CallError, Gateway
from .common import ROOT, dump, sha, load_cases, load_references
from .controller import Controller
from .evidence_compiler import source_pack
from .memory_store import MemoryStore
from .memory_writer import MemoryWriter
from .retrieval import DenseModels, Retriever
from .scoring import Scorer
from .rate_limit import DispatchStopped


def interrupted_operation(exc):
    # Scheduling/transport interruptions have no final model result. A schema or
    # scoring contract failure remains a real failure, including empty assertions.
    return isinstance(exc, DispatchStopped) or (isinstance(exc, CallError) and (
        str(exc) == 'operator_or_quota_stop_no_dispatch' or str(exc).startswith('transport_')
        or str(exc).startswith('previous_attempt_retained_transport_')))


def store_path(namespace, version="v0"):
    return ROOT / "runs" / version / "stores" / sha(namespace)[:24] / "memory.sqlite"


def case_path(uid, method, version="v0"):
    return ROOT / "runs" / version / "cells" / (sha([uid, method])[:24] + ".json")


def r0_payload(case):
    payload = {"query": case["query"], "history": case["history"]}
    if case.get("query_time"):
        payload["query_time"] = case["query_time"]
    return payload


def import_scope_r0(case, prompt):
    """Reuse only an exactly equal public request, never an approximate history match."""
    if case["benchmark"] != "memsyco" or case["category"] != "contextual_scope_control":
        return None
    oldroot = ROOT.parent / "decision_scoped_memory_alignment/strong_preference_scope_validation_20261021"
    path = oldroot / "runs/cells" / f"main__{case['native_id']}__B1__r1.json"
    if not path.exists():
        return None
    old = json.loads(path.read_text())
    if old["actor_status"] != "ok":
        return None
    key = f"main/{case['native_id']}/B1/r1/actor"
    for ledger in (oldroot / "runs").glob("**/request_ledger.json"):
        for row in json.loads(ledger.read_text()):
            if row["key"] != key or row["status"] != "ok":
                continue
            actual = json.loads((ledger.parent / row["request_path"]).read_text())
            expected = {"model": "qwen3.8-flash", "messages": [{"role": "system", "content": prompt},
                        {"role": "user", "content": json.dumps(r0_payload(case), ensure_ascii=False)}],
                        "temperature": 0, "max_tokens": 4096, "stream": True, "stream_options": {"include_usage": True}}
            if actual != expected:
                return None
            return {"answer": old["answer"], "reused_actor": {"cell": str(path), "request_ledger": str(ledger),
                     "request_key": key, "request_sha256": sha(actual), "new_actor_requests": 0},
                    "old_score": old.get("score") if old["judge_status"] == "ok" else None}
    return None


class Experiment:
    def __init__(self, version="v0", workers=10):
        self.version, self.workers = version, workers
        from .preflight import assert_frozen
        assert_frozen(version)
        self.frozen = json.loads((ROOT / "configs" / f"experiment_{version}.json").read_text())
        self.root = ROOT / "runs" / version
        self.root.mkdir(parents=True, exist_ok=True)
        self.gateway = Gateway(self.root / "api", concurrency=workers)
        self.models = DenseModels()
        self.retriever = Retriever(self.models)
        self.writer = MemoryWriter(self.gateway, self.retriever)
        self.actor = Actor(self.gateway)
        self.controller = Controller(self.gateway, self.retriever)
        self.scorer = Scorer(self.gateway)
        self.cases = load_cases(self.version)
        self.refs = load_references(self.version)
        from .opaque_ids import validate_opaque_histories
        validate_opaque_histories(self.cases)

    def build(self, case):
        report = self.root / "stores" / sha(case["namespace"])[:24] / "ingestion.json"
        if report.exists():
            return json.loads(report.read_text())
        if self.gateway.disabled or (self.gateway.root / 'STOP').exists():
            raise DispatchStopped('operator_or_quota_stop_no_dispatch')
        store = MemoryStore(store_path(case["namespace"], self.version), case["namespace"])
        try:
            result = self.writer.ingest(case["history"], store)
            dump(report, {"namespace": case["namespace"], "history_sha256": sha(case["history"]), **result})
            return result
        finally:
            store.close()

    def run_cell(self, case, method):
        path = case_path(case["uid"], method, self.version)
        row = json.loads(path.read_text()) if path.exists() else {"uid": case["uid"], "benchmark": case["benchmark"],
              "category": case["category"], "method": method, "version": self.version,
              "actor_status": "not_dispatched", "score_status": "not_dispatched"}
        if row["score_status"] != "not_dispatched" or row["actor_status"] == "failed":
            return row
        if self.gateway.disabled or (self.gateway.root / 'STOP').exists():
            return row
        key = f"{self.version}/{case['uid']}/{method}"
        try:
            if row["actor_status"] != "ok":
                if method == "R0":
                    imported = import_scope_r0(case, self.actor.prompt)
                    if imported:
                        row.update(imported)
                    else:
                        row["answer"] = self.gateway.complete(key + "/actor", self.actor.prompt, r0_payload(case), 4096)
                else:
                    store = MemoryStore(store_path(case["namespace"], self.version), case["namespace"])
                    try:
                        if method == "R1":
                            context = case["history"][-2:]
                            query = case["query"] + "\n" + "\n".join(t["content"] for t in context)
                            docs = self.retriever.search({"goal": query, "time_mode": "unspecified"}, store, status_aware=False)
                            sources = source_pack(store, docs, 24000)
                            row.update(retrieved_memory_ids=[d["id"] for d in docs], retrieved_evidence=docs,
                                       source_ids=[s["id"] for s in sources])
                            row["answer"] = self.gateway.complete(key + "/actor", self.actor.prompt,
                                {"query": case["query"], "query_time": case.get("query_time"), "context": context,
                                 "history": docs, "source_evidence": sources}, 4096)
                        else:
                            assert method == "QAMC"
                            row.update(self.controller.answer(case, store, key))
                    finally:
                        store.close()
                row["actor_status"] = "ok"
                dump(path, row)
        except Exception as exc:
            row.update(actor_status="not_dispatched" if interrupted_operation(exc) else "failed",
                       error=str(exc), error_type=type(exc).__name__,
                       operation_status="interrupted" if interrupted_operation(exc) else "failed")
            dump(path, row)
            return row
        try:
            if row.get("old_score"):
                from .memsyco_official_bridge import metric_map
                row["score"] = {"metric": "native_rubric_Qwen_judge_variant", "native": row["old_score"],
                                "metrics": metric_map(case["category"], row["old_score"]), "reused_judge": True}
            else:
                row["score"] = self.scorer.score(case, self.refs[case["uid"]], row["answer"], key)
            row["score_status"] = "ok"
        except Exception as exc:
            row.update(score_status="not_dispatched" if interrupted_operation(exc) else "failed",
                       score_error=str(exc), score_error_type=type(exc).__name__)
        dump(path, row)
        return row

    def run(self, phase):
        frozen = self.frozen
        selected = [c for c in self.cases if phase != "smoke" or c["uid"] in frozen["smoke_ids"]]
        by_namespace = {c["namespace"]: c for c in selected}
        rng = random.Random(frozen["dispatch_seed"])
        namespaces = list(by_namespace)
        rng.shuffle(namespaces)
        methods = {c["uid"]: rng.sample(["R0", "R1", "QAMC"], 3) for c in selected}
        # Completed namespaces can answer immediately; a long ingestion does not block other cases.
        # Separate executors share one API semaphore, so total live requests remain <= workers.
        builds = ThreadPoolExecutor(max_workers=self.workers)
        answers = ThreadPoolExecutor(max_workers=self.workers)
        pending_build, pending_answer = {}, {}
        try:
            pending_build = {builds.submit(self.build, by_namespace[ns]): ns for ns in namespaces}
            built, answered = 0, 0
            while pending_build or pending_answer:
                completed, _ = wait(set(pending_build) | set(pending_answer), return_when=FIRST_COMPLETED)
                for future in completed:
                    if future in pending_build:
                        ns = pending_build.pop(future)
                        try:
                            result = future.result()
                        except Exception as exc:
                            self.gateway.event(phase=phase, namespace=ns, status="ingestion_stopped", error=str(exc))
                            raise
                        built += 1
                        print(json.dumps({"stage": "ingestion", "done": built, "of": len(by_namespace), "namespace": ns, **result}), flush=True)
                        for case in selected:
                            if case["namespace"] == ns:
                                for method in methods[case["uid"]]:
                                    pending_answer[answers.submit(self.run_cell, case, method)] = (case["uid"], method)
                    else:
                        pending_answer.pop(future)
                        result = future.result()
                        answered += 1
                        print(json.dumps({"stage": "answer", "done": answered, "of": len(selected) * 3, "uid": result["uid"],
                                          "method": result["method"], "actor": result["actor_status"], "score": result["score_status"],
                                          "error": result.get("error") or result.get("score_error")}), flush=True)
        finally:
            # Cancel queued work before joining in-flight work. Cancellation has
            # no model score; the original completed artifacts remain resumable.
            for future in list(pending_build) + list(pending_answer):
                future.cancel()
            builds.shutdown(wait=True, cancel_futures=True)
            answers.shutdown(wait=True, cancel_futures=True)
            self.gateway.export()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("smoke", "development"))
    parser.add_argument("--version", default="v0")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()
    experiment = Experiment(args.version, args.workers)
    try:
        experiment.run(args.phase)
    finally:
        experiment.gateway.export()


if __name__ == "__main__":
    main()
