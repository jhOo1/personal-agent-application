"""Audit V44's decisions and inherit the grade of each exact selected answer."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_fixed_answer_choice_v44 as run
import score_task_only as task
from analyze_policy import group_stability

RP, GATE = run.stage.prior.RP, run.stage.prior.GATE
GENERIC, EVIDENCE = run.ARMS
ZERO, RULE, REVIEW = task.METHOD, "TASK_ONLY_IF_RP_HAS_NO_C", "REVIEW"
METHODS = (GENERIC, EVIDENCE, RP, GATE, ZERO, RULE, REVIEW)


def compile_choice(payload, record, raw):
    if not record or record["status"] != "OK":
        return {"status": record["status"] if record else "UNDISPATCHED"}
    try:
        answer = run.contract.execute_choice(payload, raw)
    except (ValueError, TypeError):
        return {"status": "INVALID_CHOICE", "raw": raw}
    chosen, = (c for c in payload["candidates"] if c["answer"] == answer)
    return {"status": "SELECTED", "raw": raw, "source": RP if chosen["generation_context"] == "RP" else ZERO,
            "answer_sha256": sha(answer), "choice_id": chosen["id"]}


def reconstruct():
    plan, manifest, aliases = run.artifacts()
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    received = run.probe.stage_receipts(run.STAGE)
    ledger = [record for record, _ in received.values() if record]
    if len(received) != plan["choice_request_cap"]:
        raise ValueError("Receipt expectations differ from the frozen cap")
    for row in aliases:
        origin = row["reuse"]
        record, raw = received[origin["uid"], origin["method"]]
        if record and record["request_sha256"] != row["wire_sha256"]:
            raise ValueError("An exact reuse no longer matches its recorded wire")
        received[row["uid"], row["method"]] = (record, raw)
    prior = run.read(run.stage.prior.OUT / "FROZEN.json")
    drafts = task.saved_drafts(prior)
    old_grade_plan = run.read(task.OUT / "FROZEN.json")
    archived_control = run.read(task.OUT / "RESULTS.json")
    score_rows, inherited_receipts = task.collect(old_grade_plan)
    if inherited_receipts != archived_control["ledger"]:
        raise ValueError("Historical Judge receipts changed")
    readout = {row["uid"]: row for row in archived_control["roots"]}
    scored = {row["uid"]: row for row in score_rows}
    preflight = run.read(run.stage.OUT / "FIXED_ANSWER_CHOICE_PREFLIGHT.json")
    expected = {row["uid"]: row for row in preflight["rows"]}
    rows = []
    for root in prior["roots"]:
        uid, group = root["uid"], root["group"]
        old = scored[uid]
        zero = old["native"][ZERO]
        if (zero != readout[uid]["task_only"] or old["labels"] != readout[uid]["labels"]
                or group != readout[uid]["group"]):
            raise ValueError("Historical task-only grade or source group changed")
        rp = root["archived"][RP]["answer"]
        baseline = drafts[root["task_wire_sha256"]]["answer"]
        native = {m: old["native"][m] for m in (RP, GATE, REVIEW, ZERO)}
        r = {"uid": uid, "group": group, "labels": old["labels"], "positions": old["positions"],
             "less_exposed": root["in_sensitivity"], "native": native, "choices": {}}
        native[RULE] = {**native[RP if any(p["policy"] == "C" for p in root["archived_policy"]) else ZERO]}
        if not baseline:
            r["assignment"] = "NO_USABLE_DRAFT"
            r["missing_reason"] = preflight["missing"][uid]
            decisions = {m: {"status": r["assignment"]} for m in run.ARMS}
        else:
            if sha(baseline) != old_grade_plan["ready"][uid]["answer_sha256"]:
                raise ValueError("Historical score bound to a different answer")
            r["assignment"] = expected[uid]["status"]
            if rp == baseline:
                decisions = {m: {"status": "IDENTICAL_ANSWER", "source": RP, "answer_sha256": sha(rp)} for m in run.ARMS}
            else:
                payload = run.contract.packet(root, rp, baseline)
                decisions = {m: compile_choice(payload, *received[uid, m]) for m in run.ARMS}
        for m, decision in decisions.items():
            source = decision.get("source")
            r["choices"][m] = decision
            native[m] = {**native[source], "reuse": source} if source else {"fields": {}, "raw": None}
        rows.append(r)
    return plan, rows, ledger


def grade_pair(rows, left, right, field):
    groups, paired_rows = defaultdict(lambda: [0, 0]), []
    for row in rows:
        raw = [row["native"][m]["fields"].get(field) for m in (left, right)]
        if all(isinstance(v, (float, int)) for v in raw):
            a, b = raw
            groups[row["group"]][0] += b - a
            groups[row["group"]][1] += 1
            paired_rows.append((a, b))
    if not paired_rows:
        return {"n": 0}
    a, b = map(sum, zip(*paired_rows, strict=True))
    n = len(paired_rows)
    return {"n": n, "left": a / n, "right": b / n, "delta": (b - a) / n, **group_stability(groups)}


def settlement(plan, ledger):
    runtime = run.read(run.OUT / "RUN_STATE.json")
    if (runtime.get("error") != "A durable receipt is awaiting delivery settlement"
            or len(ledger) != plan["choice_request_cap"]):
        return runtime["state"]
    recovery_path = run.OUT / "INITIAL_LAUNCH_RECOVERY.json"
    if not recovery_path.exists():
        return runtime["state"]
    recovery = run.read(recovery_path)
    expected = {r["request_sha256"] for r in recovery["retained_physical_delivery_unknown"]}
    pending = {r["request_sha256"] for r in ledger if r["status"] == "PENDING_DELIVERY_UNKNOWN"}
    if expected and pending == expected:
        return "SETTLED_WITH_RETAINED_DELIVERY_UNKNOWN"
    return runtime["state"]


def evaluate(plan, rows, ledger):
    bounds = plan["thresholds"]
    eligible = [r for r in rows if r["assignment"] != "NO_USABLE_DRAFT"]
    panels = {
        "all_assigned": rows, "eligible": eligible,
        "all_A": [r for r in eligible if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in eligible if set(r["labels"]) != {"A"}],
        "less_exposed": [r for r in eligible if r["less_exposed"]],
    }
    comparisons = {}
    for panel, sample in panels.items():
        comparisons[panel] = {other: {
            "match": run.stage.v42.paired(sample, other, EVIDENCE),
            **{field: grade_pair(sample, other, EVIDENCE, field) for field in ("OPB", "UPB", "FM")},
        } for other in METHODS if other != EVIDENCE}
        comparisons[panel]["GENERIC_vs_RP"] = {"match": run.stage.v42.paired(sample, RP, GENERIC),
                                                **{f: grade_pair(sample, RP, GENERIC, f) for f in ("OPB", "UPB", "FM")}}
    strict = [r for r in eligible if all(r["native"][m]["fields"].get("match") is not None for m in METHODS)]
    common = {}
    for method in METHODS:
        fields = [r["native"][method]["fields"] for r in strict]
        common[method] = {"matched": sum(f["match"]["matched"] for f in fields),
                          "positions": sum(f["match"]["positions"] for f in fields),
                          **{f: {"total": sum(g[f] for g in fields if f in g),
                                 "available": sum(f in g for g in fields)}
                             for f in ("OPB", "UPB", "FM", "full_match")}}
    checks = {}
    for other, key in ((GENERIC, "generic"), (RP, "original_rp"), (REVIEW, "archived_strong_review")):
        primary = comparisons["eligible"][other]["match"]
        protection = comparisons["contains_BC"][other]
        checks[other] = {
            "coverage": primary["valid_cases"] >= bounds["paired_valid_fraction_minimum"] * len(eligible),
            "match": primary.get("95pct_source_bootstrap", [-1])[0] > bounds[f"overall_match_margin_vs_{key}"],
            "bc_match": protection["match"].get("95pct_source_bootstrap", [-1])[0] >= -bounds["contains_BC_match_noninferiority_margin"],
            **{f: protection[f].get("95pct_source_bootstrap", [0, 1])[1] <= bounds["UPB_and_FM_harm_margin_points_per_answer"]
               for f in ("UPB", "FM")},
        }
    return {
        "state": settlement(plan, ledger), "frozen_roots": len(rows), "eligible_roots": len(eligible),
        "physical_requests": len(ledger), "retained_failures": [r for r in ledger if r["status"] != "OK"],
        "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in ledger),
        "unknown_usage": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger),
        "choice_counts": {m: Counter((r["choices"][m].get("source") or r["choices"][m]["status"]) for r in rows)
                          for m in run.ARMS},
        "strict_common": {"n": len(strict), "source_groups": len({r["group"] for r in strict}), "scores": common},
        "comparisons": comparisons, "advancement_checks": checks,
        "statistical_screen_pass": all(all(values.values()) for values in checks.values()),
        "new_actor_requests": 0, "new_native_judge_requests": 0, "independent_behavior_validation": False,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    plan, rows, records = reconstruct()
    results = evaluate(plan, rows, records)
    if args.save:
        if (results["state"] not in ("COMPLETE", "SETTLED_WITH_RETAINED_DELIVERY_UNKNOWN")
                or len(records) != plan["choice_request_cap"]):
            raise ValueError("Terminal output requires the settled physical panel")
        run.probe.freeze(run.OUT / "RESULTS.json", results)
        run.probe.freeze(run.OUT / "COMPLETED.json", {"rows": rows, "ledger": records})
    print(json.dumps({k: v for k, v in results.items() if k != "comparisons"}, ensure_ascii=False, indent=2))
