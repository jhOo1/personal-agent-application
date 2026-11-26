"""BenchPreS T1 three-draw comparison of frozen Strong Gate and Selectivity."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import re

import qamc_benchpres_matched_paper_run as prior
from proposals.qamc_protocol_alignment.sampling import sampling_key
from proposals.qamc_sentence_units.runtime import Runtime, frozen, read
from qamc.common import sha
from qamc.contextual_match.benchpres_native_aggregation_v2 import summarize
from qamc.contextual_match.cache import service_filtered
from qamc.contextual_match.cache_inventory import inventory
from qamc.contextual_match.component_dispatch import BudgetGate
from qamc.contextual_match.lossless_transport import filter_compatible_cache
from qamc.contextual_match.runtime_minute_policy import MinuteControl, activate
from qamc.contextual_match.usage_observability import UsageObservableSampler
from qamc.pa.core import digest
from qamc.transport_helpers import read_reference


ROOT = prior.ROOT
OUT = prior.OUT.with_name("benchpres_repeat_matched_v1")
RUN = prior.RUN.with_name(OUT.name)
GATE = "GEPA_SELECTED_BOUNDS"
PAPER = prior.METHOD
METHODS = (GATE, PAPER)
REPEATS = range(3)
WAVE_SIZE = 8
STAGES = prior.JUDGES


def action(protocol, uid, method, stage, rep, body):
    return {"unit": {"protocol_sha256": sha(protocol), "root_id": uid, "method": method,
                     "stage": stage, "replicate": rep}, "request": body}


def waves(cases):
    groups = defaultdict(list)
    for case in cases:
        groups[case["analysis_group_id"]].append(case["uid"])
    keys = sorted(groups)
    order = [uid for i in range(max(map(len, groups.values()))) for key in keys
             for uid in sorted(groups[key])[i:i + 1]]
    return [order[i:i + WAVE_SIZE] for i in range(0, len(order), WAVE_SIZE)]


def prepare():
    parent_path = prior.OUT / "PLAN.json"
    old_score_path = prior.base.OUT / "RESULT_ROWS.json"
    parent = read(parent_path)
    prior.check(parent, False)
    if any(c["independent_confirmation"] for c in parent["cases"]):
        raise ValueError("BenchPreS repeat evaluation is exposed development only")
    protocols = deepcopy(parent["protocols"])
    for block, spec in protocols.items():
        spec["namespace"] = f"{OUT.parent.name}/{OUT.name}/{block}"
    protocols["generation"]["stages"]["Actor"]["temperature"] = 1.0
    gate = {r["uid"]: r for r in read(old_score_path) if r["method"] == GATE
            and r["benchmark"] == "benchpres"}
    paper = {r["unit"]["root_id"]: r["request"] for r in parent["initial_requests"]}
    pilot = prior.paper.pilot
    old_pilot_plan = pilot.OUT / "PLAN.json"
    old_pilot_summary = pilot.OUT / "PILOT.json"
    active_reference = read_reference()[1]
    old_plan = read(old_pilot_plan)
    old_draw = {sha(r["request"]): r for r in old_plan["initial"]}
    old_answers = {r["uid"]: r for r in read(old_pilot_summary)["rows"]}
    pins = [parent_path, old_score_path, old_pilot_plan, old_pilot_summary, Path(__file__).resolve(),
            Path(prior.score.__file__).resolve(), OUT / "PROTOCOL.md"]
    jobs, inherited, unavailable = {}, {}, []
    incompatible_historical_draws = 0
    for case in parent["cases"]:
        uid = case["uid"]
        gate_wire = gate[uid].get("actor_request")
        if gate_wire and sha(gate_wire) != gate[uid]["actor_request_sha256"]:
            raise ValueError("Stored Strong Gate Actor wire changed")
        for method, original in ((GATE, gate_wire), (PAPER, paper[uid])):
            if not original:
                unavailable.extend({"unit": action(protocols["generation"], uid, method, "Actor", rep, None)["unit"],
                                    "status": "MISSING_FROZEN_ACTOR_WIRE", "answer": None,
                                    "origin": "NO_GENERATION"} for rep in REPEATS)
                continue
            if any(original[k] != paper[uid][k] for k in ("model", "temperature", "max_tokens", "stream", "stream_options")):
                raise ValueError("Historical arms differ in common Actor settings")
            body = {**original, "temperature": 1.0}
            for rep in REPEATS:
                job = action(protocols["generation"], uid, method, "Actor", rep, body)
                key = sampling_key(job["unit"])
                jobs[key] = job
                if method == PAPER and rep == 0 and sha(body) in old_draw:
                    previous = old_draw[sha(body)]
                    if previous["request"] != body:
                        raise ValueError("Historical Selectivity request hash collision")
                    old_uid = previous["unit"]["root_id"]
                    receipt_path = pilot.RUN / "outputs" / (sampling_key(previous["unit"]) + ".json")
                    receipt = read(receipt_path)
                    if receipt["request_sha256"] != sha(body) or receipt["status"] != old_answers[old_uid]["actor_status"]:
                        raise ValueError("Historical T1 output contract changed")
                    answer = receipt.get("response", {}).get("answer")
                    if receipt["status"] == "OK" and answer != old_answers[old_uid]["answer"]:
                        raise ValueError("Historical T1 answer changed")
                    origin_path = pilot.RUN / "execution/visible" / sampling_key(previous["unit"]) / "record.json"
                    pins.extend([receipt_path, origin_path])
                    if read(origin_path)["reference_config_sha256"] != active_reference:
                        incompatible_historical_draws += 1
                        continue
                    inherited[key] = {"unit": job["unit"], "request_sha256": sha(body), "status": receipt["status"],
                                      "answer": answer, "origin": "PREASSIGNED_HISTORICAL_DRAW",
                                      "original_unit": previous["unit"]}
    cap = len(jobs) - len(inherited) + len(jobs) * len(STAGES)
    if len(parent["cases"]) != 48 or len(jobs) + len(unavailable) != 288 or any(len(v) != 8 for v in waves(parent["cases"])):
        raise ValueError("Unexpected development allocation")
    return {"protocols": protocols, "cases": parent["cases"], "waves": waves(parent["cases"]),
            "generation": jobs, "inherited": inherited, "unavailable": unavailable, "physical_cap": cap,
            "reference_sha256": active_reference,
            "prior_service_reference_equal": parent["service_reference_sha256"] == active_reference,
            "incompatible_historical_draws": incompatible_historical_draws,
            "pins": {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in pins}}


def valid(plan, service=False):
    for name, fp in plan["pins"].items():
        if sha((ROOT / name).read_bytes()) != fp:
            raise ValueError(f"Frozen input changed: {name}")
    if service and read_reference()[1] != plan["reference_sha256"]:
        raise ValueError("Runtime service fingerprint differs from frozen configuration")


def sampler(path, manifest, gate):
    value = UsageObservableSampler(path, manifest)
    value.control = MinuteControl(value.control, gate)
    return value


def generate(plan, jobs, gate, area):
    protocol = plan["protocols"]["generation"]
    frozen(area / "ACTOR_MANIFEST.json", {"protocol": protocol, "units": jobs})
    execution = area / "generation/execution"
    pending = []
    for job in jobs:
        key = sampling_key(job["unit"])
        out = area / "generation/outputs" / (key + ".json")
        if out.exists():
            if read(out)["request_sha256"] != sha(job["request"]):
                raise ValueError("Retained output differs from frozen Actor wire")
        elif key in plan["inherited"]:
            frozen(out, plan["inherited"][key])
        else:
            pending.append((job, out))
    if pending:
        reader = sampler(execution, {"protocol": protocol, "units": [j for j, _ in pending]}, gate)
        try:
            def send(item):
                job, out = item
                try:
                    receipt = reader.perform(**job)
                    answer, status = receipt["response"]["answer"], "OK"
                except Exception as exc:
                    answer = None
                    rec = execution / "visible" / sampling_key(job["unit"]) / "record.json"
                    status = read(rec)["status"] if rec.exists() else type(exc).__name__
                    if status == "OK":
                        reply_path = rec.with_name("response.json")
                        answer = read(reply_path)["answer"]
                frozen(out, {"unit": job["unit"], "request_sha256": sha(job["request"]),
                             "status": status, "answer": answer, "origin": "INDEPENDENT_SAMPLING_UNIT"})
                print(f"Actor {sampling_key(job['unit'])[:10]} {status}", flush=True)

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(send, pending))
        finally:
            reader.close()
    return [read(area / "generation/outputs" / (sampling_key(j["unit"]) + ".json")) for j in jobs]


def assess(plan, actors, gate, area):
    cases = {c["uid"]: c for c in plan["cases"]}
    refs, jobs = {}, []
    protocol = plan["protocols"]["grading"]
    for actor in actors:
        if actor["status"] != "OK" or not actor["answer"]:
            continue
        u = actor["unit"]
        uid, method, rep = u["root_id"], u["method"], u["replicate"]
        case = cases[uid]
        reference = read(ROOT / case["evaluation_path"])
        if digest(reference) != case["evaluation_hash"]:
            raise ValueError("Evaluation-only label drift")
        refs[uid] = reference
        query = prior.base.task_for(case).query
        for stage, system, content in prior.score.initial_requests(ROOT, "benchpres", reference, query, actor["answer"]):
            body = prior.text_request(system, content, protocol["model"], protocol["stages"][stage]["max_tokens"])
            jobs.append(action(protocol, uid, method, stage, rep, body))
    frozen(area / "JUDGE_MANIFEST.json", {"protocol": protocol, "units": jobs})
    cachefile = area / "JUDGE_CACHE.json"
    if not cachefile.exists():
        hashes = {sha(j["request"]) for j in jobs}
        cache = service_filtered(ROOT, inventory(ROOT, hashes), hashes, plan["reference_sha256"])
        frozen(cachefile, filter_compatible_cache(ROOT, cache))
    runtime = Runtime(ROOT, area / "grading", area / "grading", lambda _p: valid(plan, True),
                      sampler_class=lambda path, manifest: sampler(path, manifest, gate))
    runtime.stage({**plan, "protocol": protocol, "allowed_unit_keys": [sampling_key(j["unit"]) for j in jobs]},
                  "repeated_benchpres", "judge", jobs, read(cachefile))
    by_draw = defaultdict(dict)
    for j in jobs:
        u = j["unit"]
        observed = runtime.output(u)
        by_draw[u["root_id"], u["method"], u["replicate"]][u["stage"]] = observed
    rows = []
    for a in actors:
        u = a["unit"]
        uid, method, rep = u["root_id"], u["method"], u["replicate"]
        receipts = by_draw[uid, method, rep]
        result = {"category": "benchpres", "uid": uid, "method": method, "replicate": rep,
                  "actor_status": a["status"], "status": a["status"] if a["status"] != "OK" else "JUDGE_UNAVAILABLE",
                  "score": None}
        if set(receipts) == set(STAGES) and all(r and r["status"] == "OK" for r in receipts.values()):
            raw = {stage: r["response"]["answer"] for stage, r in receipts.items()}
            try:
                result.update(status="SCORED", score=prior.score.grade(ROOT, "benchpres", refs[uid], raw))
            except (TypeError, ValueError, KeyError) as exc:
                result.update(status="JUDGE_INVALID", error_type=type(exc).__name__)
        rows.append(result)
    return rows


def bookkeeping(plan, rows, selected):
    cases = []
    for c in plan["cases"]:
        if c["uid"] in selected:
            ref = read(ROOT / c["evaluation_path"])
            if digest(ref) != c["evaluation_hash"]:
                raise ValueError("Frozen metrics label count cannot be verified")
            a = sum(ref["preference_label"])
            cases.append({"category": "benchpres", "uid": c["uid"], "metric_expected_aar": a, "metric_expected_mr": 5 - a})
    report = summarize(cases, METHODS, rows)
    for cut, seq in (("available_draw_pairs", [r for r in rows if r["score"]]),
                     ("all_three_draw_pairs", [r for r in rows if r["score"] and sum(
                        q["uid"] == r["uid"] and q["score"] is not None for q in rows) == 6])):
        paired = defaultdict(dict)
        for r in seq:
            paired[r["uid"], r["replicate"]][r["method"]] = r["score"]
        paired = [v for v in paired.values() if len(v) == 2]
        totals = defaultdict(Counter)
        for cell in paired:
            for method, score in cell.items():
                totals[method].update({k: score[k] for k in (
                    "aar_numerator", "aar_denominator", "mr_numerator", "mr_denominator", "task_completeness")})
                usable = [d for d in score["decisions"] if d["appropriate"] and
                          not re.search(r"\bbold\s+text\b", d["preference"], re.I)]
                totals[method].update(nonbold_hits=sum(x["label"] == "follow" for x in usable), nonbold_total=len(usable))
        report[cut] = {"task_draw_pairs": len(paired), "totals": totals}
    return report


def execute(plan, wave, area):
    selected = set(plan["waves"][wave])
    jobs = [j for j in plan["generation"].values() if j["unit"]["root_id"] in selected]
    with prior.runner_lock(prior.formal.RUN / "runner.lock"), prior.runner_lock(RUN / "runner.lock"):
        valid(plan, True)
        if (area / "RESULTS.json").exists():
            return read(area / "SUMMARY.json")
        records = [read(p) for p in RUN.glob("wave-*/*/execution/visible/*/record.json")]
        if any(r["status"] == "PENDING_DELIVERY_UNKNOWN" for r in records):
            raise RuntimeError("Existing unverified transport delivery must be retained")
        gate = BudgetGate(RUN / "PACING.json", spacing=3.2, cooldown=301, limit=plan["physical_cap"])
        activate(gate, max((r["started_unix"] + (r.get("elapsed_seconds") or 0)
                           for r in records if r["status"] != "OK"), default=0))
        actors = generate(plan, jobs, gate, area)
        actors.extend(x for x in plan["unavailable"] if x["unit"]["root_id"] in selected)
        rows = assess(plan, actors, gate, area)
        report = bookkeeping(plan, rows, selected)
        records = [read(p) for p in area.glob("*/execution/visible/*/record.json")]
        report.update(new_model_calls=len(records), request_statuses=Counter(r["status"] for r in records),
                      reported_tokens=sum((r.get("usage") or {}).get("total_tokens", 0) for r in records),
                      unknown_usage=sum("total_tokens" not in (r.get("usage") or {}) for r in records),
                      wave=wave, historical_actors=sum(a["origin"] == "PREASSIGNED_HISTORICAL_DRAW" for a in actors))
        frozen(area / "SUMMARY.json", report)
        frozen(area / "RESULTS.json", rows)
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("prepare", "run"))
    cli.add_argument("--wave", type=int, choices=range(6), default=0)
    args = cli.parse_args()
    path = RUN / "PLAN_PRIVATE.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        frozen(path, prepare())
    plan = read(path)
    valid(plan)
    print({"isolated_development_tasks": len(plan["cases"]), "three_draw_method_positions": len(plan["generation"]) + len(plan["unavailable"]),
           "missing_frozen_actor_positions": len(plan["unavailable"]),
           "preassigned_historical_draws": len(plan["inherited"]),
           "old_wire_matches_other_service": plan["incompatible_historical_draws"],
           "prior_T0_service_reference_equal": plan["prior_service_reference_equal"],
           "physical_cap": plan["physical_cap"],
           "per_wave_allocation": [len(v) for v in plan["waves"]], "plan_sha256": sha(plan)}, flush=True)
    if args.action == "run":
        area = RUN / f"wave-{args.wave}"
        result = execute(plan, args.wave, area)
        print({k: result[k] for k in ("wave", "new_model_calls", "request_statuses", "reported_tokens")})


if __name__ == "__main__":
    main()
