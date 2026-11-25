"""Run the exact direct/compiled realization contrast on two exposed transfer panels."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path

from qamc.common import parse_object, sha

import decision_realization as method
import run_decision_realization as parent
from run_realization_append_ablation import MAIN_ONLY
from transfer_edit import PANELS, archived_answers, cached_dispatch, context, matching_grading_receipts
from transfer_execution import bench, bench_pair, development_roots, grade, persist, persist_pair


OUT = parent.OUT.with_name("decision_realization_transfer_v1")
RUN = parent.RUN.with_name(OUT.name)
probe, read = parent.probe, parent.read
ARMS = (*method.METHODS, MAIN_ONLY)


def freeze_spec(reference):
    paths = (Path(__file__), Path(method.__file__), Path(parent.__file__),
             Path(__file__).with_name("REALIZATION_TRANSFER_PROTOCOL.md"),
             Path(grade.__code__.co_filename), Path(context.__code__.co_filename),
             Path(matching_grading_receipts.__code__.co_filename))
    panels = {}
    for name in PANELS:
        roots = development_roots(name)
        n = len(roots)
        stages = bench.JUDGES if name == "BenchPreS" else [persist.STAGE]
        panels[name] = {
            "roots": {root["uid"]: sha([root["public_task"], root["original_sources"],
                                      method.selector(root)]) for root in roots},
            "caps": {parent.PLAN: n, parent.ACTOR: 2 * n, **{stage: 3 * n for stage in stages}},
        }
    return {"panels": panels, "service_reference_sha256": reference,
            "input_hashes": {path.name: sha(path.read_bytes()) for path in paths},
            "independent_confirmation": False}


def evaluate(benchmark, dispatch):
    roots = development_roots(benchmark)
    counts = Counter()
    selectors = {(r["uid"], "SHARED_USES", parent.PLAN): method.selector(r) for r in roots}
    received = cached_dispatch(dispatch, selectors, {}, (), counts)
    selected = {(uid, name): (rec, rec.get("answer")) for (uid, name, _), rec in received.items()}
    frozen = {"selector_wires": {uid: sha(wire) for (uid, _, _), wire in selectors.items()}}
    traces, jobs = parent.actor_jobs(roots, selected, frozen)
    actors = cached_dispatch(dispatch, {(uid, arm, parent.ACTOR): wire for uid, arm, wire in jobs}, {}, (), counts)
    answers = []
    for root in roots:
        uid = root["uid"]
        trace = traces[uid]
        for arm in method.METHODS:
            record = actors.get((uid, arm, parent.ACTOR), {"status": "NO_VALID_SELECTOR"})
            row = {"uid": uid, "method": arm, "actor_status": record["status"], "score": None,
                   "actor_sha256": record.get("request_sha256")}
            main = None
            if record["status"] == "OK":
                try:
                    rendering = arm if trace["route"] == "SEGMENTED" else method.DIRECT
                    raw = record["answer"]
                    compiled, added, rejected = method.compile_answer(raw, trace["uses"], rendering)
                    main = parse_object(raw)["main_answer"] if rendering == method.SEGMENTED else compiled
                    if compiled != main and (not added or not compiled.startswith(main + "\n\n")):
                        raise ValueError("Removing adjustments changed the main answer")
                    row.update(answer=compiled, appended_sources=added, rejected_adjustments=rejected)
                except (KeyError, TypeError, ValueError) as error:
                    main = None
                    row.update(actor_status="INVALID_ACTOR_CONTRACT", error=str(error))
            answers.append(row)
            if arm == method.SEGMENTED:
                answers.append({**row, "method": MAIN_ONLY, "answer": main, "appended_sources": []})
    cases, protocol, controls = context(benchmark)
    if cases.keys() != traces.keys():
        raise ValueError("Scoring and generation must use the same exposed roster")
    cache, conflicts = matching_grading_receipts(benchmark, cases, protocol, archived_answers(benchmark, cases))
    scored = grade(benchmark, answers, cases, protocol,
                   lambda jobs: cached_dispatch(dispatch, jobs, cache, conflicts, counts))
    cells = {(row["uid"], row["method"]): row["score"] for row in (*scored, *controls) if row["score"] is not None}
    pair = bench_pair if benchmark == "BenchPreS" else persist_pair
    comparisons = {name: pair(name, MAIN_ONLY, cases, cells)
                   for name in (*method.METHODS, *sorted({row["method"] for row in controls}))}
    return {"assigned": len(roots), "grading_model": protocol["model"], "rows": scored, "selector": traces,
            "valid_scores": Counter(row["method"] for row in scored if row["score"] is not None),
            "comparisons": comparisons, "cache": counts,
            "appended_cases": sum(bool(row.get("appended_sources")) for row in scored)}


def dispatch_for(plan, name, live):
    def dispatch(jobs):
        stages = defaultdict(list)
        for (uid, arm, stage), wire in jobs.items():
            stages[stage].append((uid, arm, wire))
        receipts = {}
        for stage, entries in stages.items():
            modes = {(w["model"], w["max_tokens"], w["temperature"]) for _, _, w in entries}
            if len(modes) != 1 or len(entries) > plan["panels"][name]["caps"][stage]:
                raise ValueError("Requests exceed frozen capacity or mix sampling contracts")
            model, max_tokens, temperature = modes.pop()
            protocol = {"experiment": f"{OUT.name}/{name}", "model": model, "concurrency": 8,
                        "spacing_seconds": 3.2, "automatic_retries": 0,
                        "stages": {stage: {"max_tokens": max_tokens, "temperature": temperature}}}
            manifest = {"protocol": protocol, "units": [
                {"unit": {"stage": stage, "root_id": uid, "method": arm, "replicate": 0,
                          "protocol_sha256": sha(protocol)}, "request": wire}
                for uid, arm, wire in entries]}
            probe.freeze(probe.OUT / f"{stage}_MANIFEST.json", manifest)
            if live:
                parent.v42.prior.dispatch(plan, stage, manifest)
            for (uid, arm), (record, answer) in probe.stage_receipts(stage).items():
                if record is None or record["status"] == "PENDING_DELIVERY_UNKNOWN":
                    raise RuntimeError(f"Retained unconfirmed receipt in {name}/{stage}")
                receipts[uid, arm, stage] = {**record, "answer": answer}
        return receipts
    return dispatch


def main(action, name):
    path = OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, freeze_spec(probe.read_reference()[1]))
        return
    plan = read(path)
    reference = plan["service_reference_sha256"]
    live = action == "run"
    if freeze_spec(reference) != plan or (live and probe.read_reference()[1] != reference):
        raise ValueError("Frozen inputs, implementation or gateway fingerprint changed")
    probe.OUT, probe.RUN = OUT / name, RUN / name
    state = probe.OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING"})
    try:
        result = evaluate(name, dispatch_for(plan, name, live))
        records = [record for stage in plan["panels"][name]["caps"]
                   for record, _ in probe.stage_receipts(stage).values()]
        if not records or any(r is None for r in records):
            raise ValueError("Expected terminal execution receipts")
        result["physical_requests"] = len(records)
        result["transport"] = Counter(r["status"] for r in records)
        result["known_tokens"] = sum((r["usage"] or {}).get("total_tokens", 0) for r in records)
        result["unknown_usage"] = sum("total_tokens" not in (r["usage"] or {}) for r in records)
        result["ledger"] = records
        probe.freeze(probe.OUT / "SETTLED.json", result)
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(records)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    parser.add_argument("benchmark", choices=PANELS, nargs="?")
    args = parser.parse_args()
    if args.action != "freeze" and args.benchmark is None:
        parser.error("run and report require an exposed benchmark")
    with probe.runner_lock(RUN / "runner.lock"):
        main(args.action, args.benchmark)
