"""Observed workload proxies and real source reuse, never counterfactual bills.

Inputs are already exported public traces. A cached response supplies an
observed token count for a logical requirement, not a new billed request or an
independent sample. Physical dispatch ownership remains a separate report.
"""
from collections import Counter, defaultdict
from .costs import summarize_records, unit_key


PREPROCESS = {"Memory": ("R2", "R3"), "MemoryRecovery": ("R2", "R3"),
              "MemorySummary": ("R1",), "MemorySummaryRecovery": ("R1",)}
TASK = {"Task": ("R3",)}
JUDGES = {"RPEvalJudge", "PersistJudge", "BenchComplete", *(f"BenchAttr{i}" for i in range(5))}
NOMINAL = {"R0": (2, 0), "R1": (2, 1), "R2": (2, 1), "R3": (3, 1),
           "RAW": (1, 0), "QUERY_SUMMARY": (2, 0), "INCREMENTAL_UNIFIED_ADAPT": (2, 0)}


def group_for(stage):
    if stage in PREPROCESS:
        return "preprocessing"
    if stage in JUDGES:
        return "evaluation"
    return "online"


def observation(trace):
    # Backing physical latency may be unavailable for historical cache rows;
    # missing values stay absent rather than being imputed from another call.
    physical = trace.get("physical_record", {})
    response = trace.get("visible_response", {})
    return {"unit": trace["unit"], "request_sha256": trace["request_sha256"],
            "status": trace["status"], "usage": physical.get("usage") or response.get("usage"),
            "elapsed_seconds": physical.get("elapsed_seconds"),
            "automatic_retries": 0}


def workload(packets, methods):
    if len(set(methods)) != len(methods) or any(m not in NOMINAL for m in methods):
        raise ValueError("Unsupported or duplicate method in workload report")
    seen_roots = set()
    traces = {}
    origins = defaultdict(set)
    requirements = {m: defaultdict(set) for m in methods}
    uses = defaultdict(set)
    coverage = {m: Counter() for m in methods}
    availability = {m: {"read_statuses": Counter(), "actor_statuses": Counter()} for m in methods}
    representations = {}
    for packet in packets:
        uid = packet["uid"]
        if uid in seen_roots:
            raise ValueError("Repeated root packet is not another query or sample")
        seen_roots.add(uid)
        rows = {r["method"]: r for r in packet["methods"]}
        if set(rows) != set(methods) or len(rows) != len(packet["methods"]):
            raise ValueError("Packet method coverage differs")
        for method, row in rows.items():
            coverage[method]["selected_roots"] += 1
            coverage[method]["valid_scores"] += row.get("score") is not None
            coverage[method]["saved_answers"] += bool(row.get("answer"))
            availability[method]["read_statuses"][row.get("read_status", "UNKNOWN")] += 1
            availability[method]["actor_statuses"][row.get("actor_status", "UNKNOWN")] += 1
            coverage[method]["judge_contract_failures"] += bool(row.get("score_error_type"))
        for row in packet.get("representations", ()):
            key = (row["stage"], row["encoder_id"])
            if key in representations and representations[key] != row["status"]:
                raise ValueError("Shared representation validation status changed")
            representations[key] = row["status"]
        for trace in packet["visible_call_traces"]:
            stage = trace["unit"]["stage"]
            consumers = PREPROCESS.get(stage, TASK.get(stage, (trace["unit"]["method"],)))
            consumers = set(consumers) & set(methods)
            if not consumers:
                raise ValueError("Unmapped trace in workload report")
            key = unit_key(trace)
            # Unissued jobs still count as materialized logical requirements.
            # They have no observed usage, latency, or request hash proof.
            if trace["status"] == "UNISSUED":
                value = {"unit": trace["unit"], "request_sha256": None,
                         "status": "UNISSUED", "usage": None, "elapsed_seconds": None,
                         "automatic_retries": 0}
            else:
                value = observation(trace)
            if key in traces and traces[key] != value:
                raise ValueError("A shared sampling identity has inconsistent observations")
            traces[key] = value
            origins[key].add(trace.get("origin", "UNKNOWN"))
            for method in consumers:
                requirements[method][group_for(stage)].add(key)
            if stage in PREPROCESS or stage in TASK:
                uses[(stage, trace["unit"]["root_id"])].add(uid)

    def proxy(keys):
        values = [traces[k] for k in sorted(keys)]
        # summarize_records uses legacy physical field names internally. This
        # wrapper explicitly exposes logical positions to avoid fake billing.
        summary = summarize_records(values)
        summary["logical_positions"] = summary.pop("physical_requests")
        summary["nonpending_observations"] = summary.pop("terminal_requests")
        summary["pending_observations"] = summary.pop("pending_requests")
        summary["unissued_observations"] = sum(r["status"] == "UNISSUED" for r in values)
        summary["logical_origin_sets"] = dict(Counter("|".join(sorted(origins[k])) for k in keys))
        summary["positions_with_multiple_observed_origins"] = sum(len(origins[k]) > 1 for k in keys)
        # Public case packets do not certify historical transport retries.
        summary.pop("automatic_retries_reported")
        summary["token_sums_are_logical_workload_proxies_not_new_billing"] = True
        summary["latency_is_backing_request_distribution_not_end_to_end_or_new_run"] = True
        return summary

    table = []
    for method in methods:
        groups = requirements[method]
        warm, cold_extra = NOMINAL[method]
        reads = availability[method]["read_statuses"]
        validated = sum(reads[s] for s in ("OK", "VALID", "INVALID"))
        table.append({"method": method, "coverage": dict(coverage[method]),
            **{k: dict(v) for k, v in availability[method].items()},
            "selector_contract_failures": reads["INVALID"],
            "selector_validated_response_roots": validated,
            "selector_contract_failure_rate_on_validated_responses": reads["INVALID"] / validated if validated else None,
            "nominal_warm_online_calls_per_query": warm,
            "nominal_cold_additional_preprocessing_calls_per_snapshot": cold_extra,
            "nominal_counts_exclude_judges_recovery_and_do_not_assume_task_cache_hits": True,
            "preprocessing": proxy(groups["preprocessing"]),
            "warm_online": proxy(groups["online"]),
            "cold_inference_workload": proxy(groups["preprocessing"] | groups["online"]),
            "evaluation": proxy(groups["evaluation"]),
            "by_stage": [{"stage": stage, **proxy({k for bucket in groups.values() for k in bucket
                           if traces[k]["unit"]["stage"] == stage})}
                         for stage in sorted({traces[k]["unit"]["stage"] for bucket in groups.values() for k in bucket})]})
    return {"observed_roots": len(seen_roots), "methods": table,
            "representation_contracts": [{"stage": stage,
                "unique_encoder_positions": sum(s == stage for s, _ in representations),
                "statuses": dict(Counter(status for (s, _), status in representations.items() if s == stage)),
                "contract_failure_rate_on_received_responses":
                    sum(s == stage and status == "INVALID" for (s, _), status in representations.items()) /
                    sum(s == stage and status in ("OK", "INVALID") for (s, _), status in representations.items())
                    if any(s == stage and status in ("OK", "INVALID") for (s, _), status in representations.items()) else None}
                for stage in sorted({s for s, _ in representations})],
            "source_reuse": [{"stage": stage, "encoder_id": eid,
                "associated_query_roots": len(uids), "query_roots": sorted(uids),
                "consumers_are_declared_architecture_not_proof_of_semantic_use": True}
                for (stage, eid), uids in sorted(uses.items())],
            "unique_materialized_sampling_positions": len(traces),
            "cross_method_sums_must_not_be_interpreted_as_physical_call_totals": True,
            "same_wire_tokens_can_appear_in_multiple_logical_method_workloads": True,
            "unissued_or_failed_dependencies_can_reduce_materialized_online_work": True,
            "equal_cost_or_quality_proven": False,
            "new_model_calls": 0}
