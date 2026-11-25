"""Receipt-bound PersistBench repeats; evaluation only, never a generation input.

An absent Actor draw has no Judge request. Identical answers can share a Judge
within one root/replicate, but cannot create independent Actor or Judge draws.
These checks do not authenticate a provider, model weights, or native parity.
"""
from copy import deepcopy

from qamc.common import sha
from qamc.contextual_match.metrics import persist_failure_table
from qamc.contextual_match.native_repeats import build_manifest
from proposals.qamc_protocol_alignment.sampling import sampling_key, validate_public_request


REPEATS = {"cross_domain": 3, "sycophancy": 3, "beneficial_memory_usage": 1}


def _allocation(cases, methods):
    if not cases or not methods or len(set(methods)) != len(methods):
        raise ValueError("Explicit roots and method priority required")
    if any(set(c) != {"uid", "category", "group_id"} or c["category"] not in REPEATS
           or not isinstance(c["uid"], str) or not c["uid"]
           or not isinstance(c["group_id"], str) or not c["group_id"] for c in cases):
        raise ValueError("Only declared PersistBench allocation metadata is accepted")
    if len({c["uid"] for c in cases}) != len(cases):
        raise ValueError("Duplicate root")
    return [(c, method, replicate) for c in cases for method in methods
            for replicate in range(REPEATS[c["category"]])]


def audit_receipts(manifest, outputs, receipts):
    """Match saved logical successes to independent public physical triplets.

    outputs and receipts are keyed by sampling_key, not request-body hash.
    Receipts contain request/record/response, read from the declared unit's
    visible directory by a caller. Missing/failed draws stay unavailable.
    """
    jobs = {}; protocol = manifest["protocol"]
    for job in manifest["units"]:
        unit, body = job["unit"], job["request"]
        key = sampling_key(unit); validate_public_request(body)
        config = protocol["stages"][unit["stage"]]
        if (key in jobs or unit["protocol_sha256"] != sha(protocol)
                or body["model"] != protocol["model"]
                or body["temperature"] != config["temperature"]
                or body["max_tokens"] != config["max_tokens"]
                or body.get("stream") is not True
                or body.get("stream_options") != {"include_usage": True}):
            raise ValueError("Changed or duplicate native sampling identity")
        jobs[key] = job
    if (manifest["maximum_physical_dispatches"] != len(jobs)
            or manifest["cross_replicate_body_cache"] is not False
            or manifest["historical_body_cache"] is not False
            or not set(outputs) <= jobs.keys() or not set(receipts) <= jobs.keys()):
        raise ValueError("Outputs or receipts exceed independent allocation")
    result = {}
    for key, job in jobs.items():
        unit, body = job["unit"], job["request"]
        output, receipt = outputs.get(key), receipts.get(key)
        if output is not None and (output["unit"] != unit or output["request_sha256"] != sha(body)
                                   or output["status"] not in {"OK", "FAILED_OR_RETAINED"}):
            raise ValueError("Logical output belongs to another draw")
        if receipt is not None:
            record = receipt["record"]
            if (set(receipt) != {"request", "record", "response"}
                    or receipt["request"] != body or record["unit"] != unit
                    or record["request_sha256"] != sha(body)):
                raise ValueError("Physical receipt belongs to another draw")
        available = output is not None and output["status"] == "OK"
        if available:
            response = output["response"]
            if (receipt is None or output.get("sample_key") != key
                    or receipt["record"]["status"] != "OK"
                    or receipt["record"].get("received_done") is not True
                    or response != receipt["response"]
                    or not isinstance(response.get("answer"), str) or not response["answer"].strip()
                    or response.get("finish_reason") != "stop" or response.get("model") != body["model"]):
                raise ValueError("Success lacks its own completed physical response")
        result[key] = {"available": available, "answer": output["response"]["answer"] if available else None,
                       "request_sha256": sha(body), "unit": unit,
                       "logical_status": output["status"] if output is not None else "UNISSUED_OR_UNCOMMITTED",
                       "physical_status": receipt["record"]["status"] if receipt is not None else None}
    return result


def _actor_inputs(cases, methods, manifest):
    # Rebuild every declared Actor slot; no absent repeat can be silently filled.
    slots = _allocation(cases, methods)
    if manifest["protocol"]["repeat_policy"] != REPEATS:
        raise ValueError("Native PersistBench repetition policy changed")
    jobs = {sampling_key(j["unit"]): j for j in manifest["units"]}
    requests = {c["uid"]: {m: {} for m in methods} for c in cases}; seen = set()
    for row in manifest["assignments"]:
        uid, method, replicate = row["root_id"], row["method"], row["replicate"]
        slot = uid, method, replicate
        if slot in seen or uid not in requests or method not in methods or row["sample_key"] not in jobs:
            raise ValueError("Actor assignment has duplicate or unknown slot")
        seen.add(slot); requests[uid][method][replicate] = jobs[row["sample_key"]]["request"]
    rebuilt = build_manifest([{k: c[k] for k in ("uid", "category")} for c in cases],
                             requests, methods, manifest["protocol"], "Actor")
    if rebuilt != manifest or len(seen) != len(slots):
        raise ValueError("Actor manifest is not the complete frozen allocation")
    return {(r["root_id"], r["method"], r["replicate"]): r for r in manifest["assignments"]}


def build_persist_judges(cases, methods, actor_manifest, actor_outputs, actor_receipts,
                         judge_protocol, judge_request):
    """Build only Judges for actual successful independent Actor draws.

    judge_request(uid, category, answer) is the locked evaluation adapter. Its
    complete returned request is frozen, including the actual answer. A failed
    upstream draw has an explicit skipped slot and never a fabricated answer.
    """
    assignments = _actor_inputs(cases, methods, actor_manifest)
    actors = audit_receipts(actor_manifest, actor_outputs, actor_receipts)
    if judge_protocol["repeat_policy"] != REPEATS:
        raise ValueError("Judge repetition policy changed")
    units, logical, skipped = [], [], []
    for case in cases:
        for replicate in range(REPEATS[case["category"]]):
            groups = {}
            for method in methods:
                slot = assignments[(case["uid"], method, replicate)]
                actor = actors[slot["sample_key"]]
                link = {"root_id": case["uid"], "category": case["category"], "method": method,
                        "replicate": replicate, "actor_sample_key": slot["sample_key"]}
                if not actor["available"]:
                    skipped.append({**link, "reason": "ACTOR_UNAVAILABLE"}); continue
                body = judge_request(case["uid"], case["category"], actor["answer"])
                validate_public_request(body)
                settings = judge_protocol["stages"]["PersistJudge"]
                if (body["model"] != judge_protocol["model"]
                        or body["temperature"] != settings["temperature"]
                        or body["max_tokens"] != settings["max_tokens"]
                        or body.get("stream") is not True
                        or body.get("stream_options") != {"include_usage": True}):
                    raise ValueError("Judge request differs from frozen scorer settings")
                groups.setdefault(sha(body), {"request": deepcopy(body), "links": []})["links"].append(
                    {**link, "actor_answer_sha256": sha(actor["answer"])})
            for group in groups.values():
                unit = {"protocol_sha256": sha(judge_protocol), "root_id": case["uid"],
                        "method": group["links"][0]["method"], "replicate": replicate, "stage": "PersistJudge"}
                key = sampling_key(unit); units.append({"unit": unit, "request": group["request"]})
                logical.extend({**link, "sample_key": key, "request_sha256": sha(group["request"]),
                                "stage": "PersistJudge"} for link in group["links"])
    return {"protocol": deepcopy(judge_protocol), "units": units, "assignments": logical,
            "skipped_upstream_draws": skipped, "root_count": len(cases),
            "all_planned_method_draws": len(_allocation(cases, methods)),
            "maximum_physical_dispatches": len(units), "cross_replicate_body_cache": False,
            "historical_body_cache": False, "native_judge_provider_parity_proven": False,
            "actor_manifest_sha256": sha(actor_manifest)}


def persist_report(cases, methods, actor_manifest, actor_outputs, actor_receipts,
                   judge_manifest, judge_outputs, judge_receipts, judge_request, decode_score):
    """Rebuild scoring inputs, preserve all missing slots, then apply strict FR.

    decode_score(category, visible_judge_answer) is the versioned parser; only
    its structured rating counts. A prose reason cannot override that rating.
    """
    rebuilt = build_persist_judges(cases, methods, actor_manifest, actor_outputs, actor_receipts,
                                   judge_manifest["protocol"], judge_request)
    if rebuilt != judge_manifest:
        raise ValueError("Judge inputs do not match the saved actual Actor answers")
    judges = audit_receipts(judge_manifest, judge_outputs, judge_receipts)
    index = {(r["root_id"], r["method"], r["replicate"]): r for r in judge_manifest["assignments"]}
    skipped = {(r["root_id"], r["method"], r["replicate"]): r
               for r in judge_manifest["skipped_upstream_draws"]}
    rows = {m: [] for m in methods}
    for case in cases:
        for method in methods:
            ratings, trace = [], []
            for replicate in range(REPEATS[case["category"]]):
                link = index.get((case["uid"], method, replicate)); rating = None; error = None
                saved = judges[link["sample_key"]] if link else None
                status = "ACTOR_UNAVAILABLE" if link is None else "JUDGE_UNAVAILABLE"
                if saved and saved["available"]:
                    try:
                        rating = decode_score(case["category"], saved["answer"])["rating"]
                        maximum = 3 if case["category"] == "beneficial_memory_usage" else 5
                        if type(rating) is not int or not 1 <= rating <= maximum:
                            raise ValueError("Invalid structured Judge rating")
                        status = "SCORED"
                    except (ValueError, KeyError, TypeError) as exc:
                        rating = None; error = type(exc).__name__; status = "JUDGE_CONTRACT_ERROR"
                ratings.append(rating)
                actor_link = link or skipped[(case["uid"], method, replicate)]
                trace.append({"replicate": replicate, "status": status, "score_error_type": error,
                              "actor_sample_key": actor_link["actor_sample_key"],
                              "judge_sample_key": link["sample_key"] if link else None})
            rows[method].append({**case, "scores": ratings, "draws": trace})
    return {"by_method": {m: {"rows": rows[m], "metrics": persist_failure_table(rows[m])} for m in methods},
            "actor_manifest_sha256": sha(actor_manifest), "judge_manifest_sha256": sha(judge_manifest),
            "native_repeat_structure_checked": True, "native_judge_provider_parity_proven": False,
            "not_a_native_SOTA_claim": True, "new_model_calls": 0}
