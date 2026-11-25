"""Engineering acceptance for the frozen real smoke; never gates on answer quality."""
from __future__ import annotations

import json
from collections import Counter

from .common import ROOT, dump, sha, load_cases, load_references
from .memory_store import MemoryStore
from .preflight import assert_frozen
from .report import read


def smoke_gate(version):
    assert_frozen(version)
    conf = json.loads((ROOT / "configs" / f"experiment_{version}.json").read_text())
    cases = {c["uid"]: c for c in load_cases(version) if c["uid"] in conf["smoke_ids"]}
    cells, ledger = read(version)
    errors = []
    ingestion = []
    for case in cases.values():
        folder = ROOT / "runs" / version / "stores" / sha(case["namespace"])[:24]
        path = folder / "ingestion.json"
        if not path.exists():
            errors.append("missing_ingestion:" + case["uid"])
            continue
        record = json.loads(path.read_text())
        ingestion.append(record)
        if record["source_count"] != len(case["history"]) or record["history_sha256"] != sha(case["history"]):
            errors.append("source_coverage_or_hash:" + case["uid"])
    all_chunks = sum(r["chunks"] for r in ingestion)
    good_chunks = sum(r["successful_chunks"] for r in ingestion)
    if all_chunks == 0 or good_chunks / all_chunks < .95:
        errors.append("writer_engineering_coverage_below_95_percent")
    qamc = [cells.get((uid, "QAMC")) for uid in cases]
    generated = sum(bool(c and c["actor_status"] == "ok") for c in qamc)
    scored = sum(bool(c and c["score_status"] == "ok") for c in qamc)
    if generated < 6 or scored < 6:
        errors.append("insufficient_QAMC_pipeline_coverage_6_of_7")
    for row in ledger:
        if row.get("disable_model"):
            errors.append("quota_or_auth_stop")
        if row["status"] == "pending_delivery_unknown":
            errors.append("request_still_in_flight")
        if row["status"] == "ok" and (row.get("returned_model") != "qwen3.8-flash" or row.get("finish_reason") != "stop" or row.get("usage") is None):
            errors.append("accepted_response_identity_or_usage_contract")
    if sum(r.get("error") == "finish_length" for r in ledger) > 1:
        errors.append("recurrent_output_truncation")
    validated_quotes = 0
    for case in cases.values():
        cell = cells.get((case["uid"], "QAMC"))
        if not cell or cell["actor_status"] != "ok":
            continue
        store = MemoryStore(ROOT / "runs" / version / "stores" / sha(case["namespace"])[:24] / "memory.sqlite", case["namespace"])
        try:
            for item in cell["memory_view"]["evidence"]:
                sources = [store.source(s) for s in item["source_ids"]]
                if not all(sources) or not any(item["quote"] in s["content"] for s in sources):
                    errors.append("invalid_final_view_provenance:" + case["uid"])
                else:
                    validated_quotes += 1
            if len(cell["retrieval_rounds"]) > conf["max_retrieval_rounds"]:
                errors.append("retrieval_round_limit")
        finally:
            store.close()
    result = {"version": version, "passed": not errors, "engineering_errors": sorted(set(errors)),
              "smoke_cases": len(cases), "QAMC_generated": generated, "QAMC_scored": scored,
              "writer_successful_chunks": good_chunks, "writer_planned_chunks": all_chunks,
              "validated_final_evidence_quotes": validated_quotes,
              "request_statuses": dict(Counter(r["status"] for r in ledger)),
              "answer_correctness_used_for_gate": False,
              "thresholds_frozen_before_dispatch": "writer >=95%; QAMC pipeline >=6/7; no quota/auth, recurrent truncation or provenance failure"}
    dump(ROOT / "reports" / version / "SMOKE_GATE.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result
