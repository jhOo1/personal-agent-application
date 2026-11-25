"""Test communication-act binding with one shared Selector on exposed BenchPreS."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

from qamc.common import sha

import communication_binding as binding
import run_realization_transfer as archive
from settle_joint_planning import usage
from settle_realization_transfer import bench_comparison
from transfer_edit import archived_answers, cached_dispatch, matching_grading_receipts
from transfer_execution import grade


BENCH = "BenchPreS"
OLD_OUT, OLD_RUN = archive.OUT, archive.RUN
OUT, RUN = OLD_OUT.with_name("communication_binding_benchpres_v1"), OLD_RUN.with_name("communication_binding_benchpres_v1")
OPEN, BOUND = "SAME_SELECTOR_UNBOUND", "COMMUNICATION_BOUND"
SELECT, ACTOR = archive.parent.PLAN, archive.parent.ACTOR
ARMS = ((OPEN, "plain"), (BOUND, "bound"))
probe, read = archive.probe, archive.read


def prepare():
    roots = archive.development_roots(BENCH)
    jobs = {(root["uid"], "BOTH", SELECT): binding.selector(root) for root in roots}
    old_plan = read(OLD_OUT / "FROZEN.json")
    paths = (Path(__file__), Path(binding.__file__), Path(__file__).with_name("COMMUNICATION_BINDING_PROTOCOL.md"),
             OLD_OUT / "FROZEN.json", OLD_OUT / BENCH / "SETTLED.json", Path(binding.base.__file__),
             Path(archive.__file__), Path(grade.__code__.co_filename))
    n = len(roots)
    caps = {SELECT: n, ACTOR: 2 * n, **{s: 2 * n for s in archive.bench.JUDGES}}
    return {"panels": {BENCH: {"caps": caps, "roots": {key[0]: sha(wire) for key, wire in jobs.items()}}},
            "implementation": {str(p.relative_to(Path(__file__).resolve().parents[3])): sha(p.read_bytes()) for p in paths},
            "service_reference_sha256": old_plan["service_reference_sha256"],
            "nonregression": {"aar": .02, "completeness": .10}, "independent_confirmation": False}, roots, jobs


def previous_receipts(plan):
    probe.OUT, probe.RUN = OLD_OUT / BENCH, OLD_RUN / BENCH
    old = {}
    for name in plan["panels"][BENCH]["caps"]:
        for record, raw in probe.stage_receipts(name).values():
            if record is None or record["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise ValueError("Old BenchPreS archive is not terminal")
            old[name, record["request_sha256"]] = (record, raw)
    return old


def answer_rows(roots, selections, dispatch, counts):
    traces, jobs = {}, {}
    for root in roots:
        uid = root["uid"]
        record = selections[uid, "BOTH", SELECT]
        trace = traces[uid] = {"status": record["status"], "request_sha256": record["request_sha256"],
                               "raw": record.get("answer")}
        if record["status"] != "OK":
            continue
        try:
            trace.update(binding.compile_views(root, record["answer"]))
        except (ValueError, KeyError, TypeError):
            trace["status"] = "INVALID_SELECTOR_CONTRACT"
            continue
        for arm, view in ARMS:
            jobs[uid, arm, ACTOR] = binding.base.actor(root, trace[view], binding.base.DIRECT)
    actors = cached_dispatch(dispatch, jobs, {}, (), counts)
    rows = []
    for uid in traces:
        for arm, _ in ARMS:
            rec = actors.get((uid, arm, ACTOR), {"status": "NO_VALID_SELECTOR"})
            rows.append({"uid": uid, "method": arm, "actor_status": rec["status"], "answer": rec.get("answer"),
                         "actor_sha256": rec.get("request_sha256"), "score": None})
    return rows, traces


def evaluate(plan, roots, jobs, dispatch, aliases):
    counts = Counter()
    selections = cached_dispatch(dispatch, jobs, {}, (), counts)
    rows, traces = answer_rows(roots, selections, dispatch, counts)
    cases, protocol, controls = archive.context(BENCH)
    if cases.keys() != traces.keys():
        raise ValueError("Generation and scoring rosters differ")
    score_cache, conflicts = matching_grading_receipts(BENCH, cases, protocol, archived_answers(BENCH, cases))
    grade(BENCH, rows, cases, protocol, lambda items: cached_dispatch(dispatch, items, score_cache, conflicts, counts))
    prior = [r for r in read(OLD_OUT / BENCH / "SETTLED.json")["rows"] if r["method"] == archive.MAIN_ONLY]
    scores = {(r["uid"], r["method"]): r["score"] for r in (*rows, *controls, *prior) if r["score"] is not None}
    comparisons = {}
    for arm in (OPEN, archive.MAIN_ONLY, *sorted({r["method"] for r in controls})):
        pairs = [(cases[uid], scores[uid, arm], scores[uid, BOUND]) for uid in cases
                 if (uid, arm) in scores and (uid, BOUND) in scores]
        comparisons[arm] = bench_comparison(pairs)
    limit = plan["nonregression"]
    target = comparisons[OPEN]
    passed = (bool(target) and target["mr"]["source_ci95"] is not None and target["mr"]["source_ci95"][1] < 0
              and target["aar"]["delta"] is not None and target["aar"]["delta"] >= -limit["aar"]
              and target["completeness"]["delta"] >= -limit["completeness"])
    return {"rows": rows, "selector": traces, "comparisons": comparisons, "valid": Counter(
        r["method"] for r in rows if r["score"] is not None), "same_selector_screen_pass": passed,
            "dedup": counts, "reuse_prior_receipts": aliases, "independent_confirmation": False}


def main(action):
    plan, roots, jobs = prepare()
    path = OUT / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, plan)
        return
    live = action == "run"
    if read(path) != plan or (live and probe.read_reference()[1] != plan["service_reference_sha256"]):
        raise ValueError("Frozen selector, source or service changed")
    old = previous_receipts(plan)
    probe.OUT, probe.RUN = OUT / BENCH, RUN / BENCH
    archive.OUT = OUT
    stage = archive.dispatch_for(plan, BENCH, live)
    aliases = {}

    def dispatch(items):
        result, outgoing = {}, {}
        for key, wire in items.items():
            digest = sha(wire)
            if (key[2], digest) in old:
                rec, raw = old[key[2], digest]
                result[key] = {**rec, "answer": raw}
                aliases["/".join(key)] = {"sha256": digest, "status": rec["status"]}
            else:
                outgoing[key] = wire
        return {**result, **(stage(outgoing) if outgoing else {})}

    state = probe.OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING"})
    try:
        result = evaluate(plan, roots, jobs, dispatch, aliases)
        records = [record for name in plan["panels"][BENCH]["caps"]
                   for record, _ in probe.stage_receipts(name).values()]
        if any(record is None or record["status"] == "PENDING_DELIVERY_UNKNOWN" for record in records):
            raise RuntimeError("Retained an indeterminate delivery")
        used = usage(records)
        probe.freeze(probe.OUT / "SETTLED.json", {**result, "ledger": records, "usage": used})
    except (OSError, RuntimeError, ValueError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(records)})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    with probe.runner_lock(RUN / "runner.lock"):
        main(parser.parse_args().action)
