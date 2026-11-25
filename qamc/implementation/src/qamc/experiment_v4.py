"""Resumable, disjoint 120-case v4 comparison with separate writer stores."""
from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from .actor import Actor
from .api import Gateway
from .common import ROOT, dump, load_cases, load_references, sha
from .controller import Controller
from .controller_v4 import ControllerV4
from .evidence_compiler import source_pack
from .experiment import interrupted_operation, r0_payload
from .memory_store import MemoryStore
from .memory_writer import MemoryWriter
from .memory_writer_v4 import MemoryWriterV4
from .retrieval import DenseModels, Retriever
from .scoring import Scorer

VERSION = "v0_18"
METHODS = ("R0", "R1", "R2", "R3", "R4")


def store_path(namespace: str, policy: str):
    return ROOT / "runs" / VERSION / f"stores_{policy}" / sha(namespace)[:24] / "memory.sqlite"


def cell_path(uid: str, method: str):
    return ROOT / "runs" / VERSION / "cells" / (sha([uid, method])[:24] + ".json")


class ExperimentV4:
    def __init__(self, workers=4):
        from .preflight import assert_frozen
        assert_frozen(VERSION)
        self.config = json.loads((ROOT / f"configs/experiment_{VERSION}.json").read_text())
        self.root = ROOT / "runs" / VERSION
        self.root.mkdir(parents=True, exist_ok=True)
        self.gateway = Gateway(self.root / "api", concurrency=workers)
        self.old_writer_gateway = Gateway(self.root / "api_oldwriter", concurrency=workers)
        self.new_writer_gateway = Gateway(self.root / "api_newwriter", concurrency=workers)
        self.retriever = Retriever(DenseModels())
        self.old_writer = MemoryWriter(self.old_writer_gateway, self.retriever)
        self.new_writer = MemoryWriterV4(self.new_writer_gateway, self.retriever)
        self.actor = Actor(self.gateway)
        self.actor.prompt = (ROOT / "prompts/actor_common_v4.md").read_text()
        self.old_controller = Controller(self.gateway, self.retriever)
        self.old_controller.actor.prompt = self.actor.prompt
        self.new_controller = ControllerV4(self.gateway, self.retriever)
        self.new_controller.actor.prompt = self.actor.prompt
        self.scorer = Scorer(self.gateway)
        self.cases = load_cases(VERSION)
        self.refs = load_references(VERSION)
        from .opaque_ids import validate_opaque_histories
        validate_opaque_histories(self.cases)
        self.workers = workers

    def build(self, case, policy):
        report = self.root / f"stores_{policy}" / sha(case["namespace"])[:24] / "ingestion.json"
        if report.exists():
            return json.loads(report.read_text())
        gateway, writer = ((self.old_writer_gateway, self.old_writer) if policy == "old"
                           else (self.new_writer_gateway, self.new_writer))
        if gateway.disabled or (gateway.root / "STOP").exists():
            raise RuntimeError("writer_gateway_stopped")
        store = MemoryStore(store_path(case["namespace"], policy), case["namespace"])
        try:
            result = writer.ingest(case["history"], store)
            dump(report, {"namespace": case["namespace"], "policy": policy,
                          "history_sha256": sha(case["history"]), **result})
            return result
        finally:
            store.close()

    def run_cell(self, case, method):
        path = cell_path(case["uid"], method)
        row = json.loads(path.read_text()) if path.exists() else {
            "uid": case["uid"], "benchmark": case["benchmark"], "category": case["category"],
            "method": method, "version": VERSION, "actor_status": "not_dispatched", "score_status": "not_dispatched"}
        if row["score_status"] != "not_dispatched" or row["actor_status"] == "failed":
            return row
        if self.gateway.disabled or (self.gateway.root / "STOP").exists():
            return row
        key = f"{VERSION}/{case['uid']}/{method}"
        try:
            if row["actor_status"] != "ok":
                if method == "R0":
                    payload = r0_payload(case)
                    # This is an explicit capacity gate, not a silently shortened full-history baseline.
                    row["history_utf8_bytes"] = len(json.dumps(payload, ensure_ascii=False).encode())
                    row["answer"] = self.gateway.complete(key + "/actor", self.actor.prompt, payload, 4096)
                else:
                    policy = "new" if method == "R4" else "old"
                    store = MemoryStore(store_path(case["namespace"], policy), case["namespace"])
                    try:
                        if method == "R1":
                            context = case["history"][-2:]
                            query = case["query"] + "\n" + "\n".join(t["content"] for t in context)
                            docs = self.retriever.search({"goal": query, "time_mode": "unspecified"}, store,
                                                         status_aware=False)
                            sources = source_pack(store, docs, 24000)
                            row.update(retrieved_memory_ids=[d["id"] for d in docs],
                                       retrieved_evidence=docs, source_ids=[s["id"] for s in sources])
                            row["answer"] = self.gateway.complete(key + "/actor", self.actor.prompt,
                                {"query": case["query"], "query_time": case.get("query_time"), "context": context,
                                 "history": docs, "source_evidence": sources}, 4096)
                        elif method == "R2":
                            row.update(self.old_controller.answer(case, store, key))
                        elif method in ("R3", "R4"):
                            row.update(self.new_controller.answer(case, store, key))
                        else:
                            raise ValueError("unknown_method")
                    finally:
                        store.close()
                row["actor_status"] = "ok"
                dump(path, row)
        except Exception as exc:
            row.update(actor_status="not_dispatched" if interrupted_operation(exc) else "failed",
                       error=str(exc), error_type=type(exc).__name__)
            dump(path, row)
            return row
        try:
            row["score"] = self.scorer.score(case, self.refs[case["uid"]], row["answer"], key)
            row["score_status"] = "ok"
        except Exception as exc:
            row.update(score_status="not_dispatched" if interrupted_operation(exc) else "failed",
                       score_error=str(exc), score_error_type=type(exc).__name__)
        dump(path, row)
        return row

    def run(self, phase):
        # Old-store read comparison is finished before the new Writer builds start.
        if phase == "read":
            methods, policy = METHODS[:4], "old"
        elif phase == "writer":
            methods, policy = ("R4",), "new"
        else:
            raise ValueError("phase must be read or writer")
        by_namespace = {c["namespace"]: c for c in self.cases}
        rng = random.Random(self.config["dispatch_seed"])
        namespaces = list(by_namespace)
        rng.shuffle(namespaces)
        # Short histories first give a bounded early mechanism signal without
        # excluding any of the frozen long-history cases. Existing chunk markers resume.
        from .memory_writer import chunks
        namespaces.sort(key=lambda ns: sum(1 for _ in chunks(by_namespace[ns]["history"])))
        by_cases = {}
        for case in self.cases:
            by_cases.setdefault(case["namespace"], []).append(case)
        answer_workers = 4 if phase == "read" else 2
        with ThreadPoolExecutor(max_workers=self.workers) as builders, ThreadPoolExecutor(max_workers=answer_workers) as answers:
            pending_build = {builders.submit(self.build, by_namespace[ns], policy): ns for ns in namespaces}
            pending_answer = {}
            while pending_build or pending_answer:
                finished, _ = wait(set(pending_build) | set(pending_answer), return_when=FIRST_COMPLETED)
                for future in finished:
                    if future in pending_build:
                        ns = pending_build.pop(future)
                        try:
                            result = future.result()
                        except Exception as exc:
                            # One failed namespace does not erase or invalidate
                            # independent completed namespaces.
                            dump(self.root / f"stores_{policy}" / sha(ns)[:24] / "build_error.json",
                                 {"namespace": ns, "phase": phase, "error": str(exc),
                                  "error_type": type(exc).__name__, "request_records_preserved": True})
                            print(json.dumps({"stage": "ingestion", "phase": phase,
                                              "namespace": ns, "status": "interrupted",
                                              "error": str(exc)}), flush=True)
                            continue
                        print(json.dumps({"stage": "ingestion", "phase": phase, "namespace": ns,
                                          "status": result["status"], "failed_chunks": result["failed_chunks"]}), flush=True)
                        for case in by_cases[ns]:
                            for method in methods:
                                # R0 is independently dispatched against the same
                                # frozen inputs; avoid a concurrent duplicate key.
                                if method == "R0":
                                    continue
                                pending_answer[answers.submit(self.run_cell, case, method)] = (case["uid"], method)
                    else:
                        pending_answer.pop(future)
                        row = future.result()
                        print(json.dumps({"stage": "answer", "phase": phase, "uid": row["uid"],
                                          "method": row["method"], "actor": row["actor_status"],
                                          "score": row["score_status"],
                                          "error": row.get("error") or row.get("score_error")}), flush=True)

    def export(self):
        for gateway in (self.gateway, self.old_writer_gateway, self.new_writer_gateway):
            gateway.export()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("read", "writer"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    exp = ExperimentV4(args.workers)
    try:
        exp.run(args.phase)
    finally:
        exp.export()


if __name__ == "__main__":
    main()
