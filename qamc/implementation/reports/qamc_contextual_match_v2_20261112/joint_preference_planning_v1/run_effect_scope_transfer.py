"""Run the frozen effect compiler on the exposed transfer panels."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import canonical, sha, token_estimate

from effect_scope_transfer import core, generate, persist_drafts, transfer, verify
from settle_joint_planning import usage


OUT = core.OUT.with_name("effect_scope_transfer_v1")
RUN = core.RUN.with_name(OUT.name)
probe, read = core.probe, core.read


def prepare():
    plans, inputs = {}, {}
    reference = read(core.OUT / "FROZEN.json")["service_reference_sha256"]
    for benchmark in transfer.PANELS:
        panel = transfer.development_roots(benchmark)
        roots = {r["uid"]: r for r in panel}
        archive = transfer.archived_answers(benchmark, roots)
        if benchmark == "BenchPreS":
            baseline = transfer.draft_wires(panel)
            cached = {}
            judge_stages = transfer.bench.JUDGES
            ranked = 4 * len(roots)
        else:
            baseline = {}
            cached = persist_drafts(panel, archive)
            judge_stages = (transfer.persist.STAGE,)
            ranked = 3 * len(cached)
        stage_caps = {
            **({transfer.DRAFT: len(baseline)} if baseline else {}),
            core.STAGE: 2 * (len(baseline) + len(cached)),
            **{stage: ranked for stage in judge_stages},
        }
        plans[benchmark] = {
            "roster": {uid: sha([r["public_task"], r["original_sources"]]) for uid, r in roots.items()},
            "task_draft_requests": {uid: sha(w) for (uid, _, _), w in baseline.items()},
            "no_memory_reuse": {uid: {"wire": v["sha256"], "answer": sha(v["answer"])} for uid, v in cached.items()},
            "caps": stage_caps,
        }
        inputs[benchmark] = (panel, archive, baseline, cached)
    base = Path(__file__).resolve().parents[3]
    paths = (
        Path(__file__), Path(generate.__code__.co_filename), Path(core.__file__),
        Path(core.method.__file__), Path(core.method.linked.__file__),
        Path(transfer.__file__), Path(transfer.grade.__code__.co_filename),
        Path(__file__).with_name("EFFECT_SCOPE_TRANSFER_PROTOCOL.md"), core.OUT / "FROZEN.json",
        transfer.bench.OUT / "PLAN.json", transfer.persist.AUTHOR_OUT / "PLAN.json",
        core.OUT / "TRANSFER_PREFLIGHT.json",
    )
    return {
        "panels": plans, "service_reference_sha256": reference, "independent_confirmation": False,
        "inputs_sha256": {str(p.resolve().relative_to(base)): sha(p.read_bytes()) for p in paths},
    }, inputs


def stage_dispatch(plan, benchmark, *, live):
    caps = plan["panels"][benchmark]["caps"]

    def dispatch(jobs):
        staged = defaultdict(list)
        for (uid, arm, stage), wire in jobs.items():
            staged[stage].append((uid, arm, wire))
        results = {}
        for stage, entries in staged.items():
            configs = {(w["model"], w["max_tokens"], w["temperature"]) for _, _, w in entries}
            if len(configs) != 1 or len(entries) > caps.get(stage, 0):
                raise ValueError("Transfer exceeds its frozen allocation or mixes configurations")
            if any(token_estimate(canonical(w["messages"])) > 32768 for _, _, w in entries):
                raise ValueError("Transfer input exceeds its frozen limit")
            model, cap, temp = configs.pop()
            protocol = {"experiment": f"{OUT.name}/{benchmark}", "model": model, "concurrency": 8,
                        "spacing_seconds": 3.2, "automatic_retries": 0,
                        "stages": {stage: {"max_tokens": cap, "temperature": temp}}}
            manifest = {"protocol": protocol, "units": [
                {"unit": {"root_id": uid, "method": arm, "stage": stage, "replicate": 0,
                          "protocol_sha256": sha(protocol)}, "request": wire}
                for uid, arm, wire in entries]}
            probe.freeze(probe.OUT / f"{stage}_MANIFEST.json", manifest)
            if live:
                core.replay.prior.dispatch(plan, stage, manifest)
            staged_receipts = probe.stage_receipts(stage)
            for uid, arm, wire in entries:
                record, answer = staged_receipts[uid, arm]
                if record is None or record["status"] == "PENDING_DELIVERY_UNKNOWN":
                    raise RuntimeError(f"Unsettled receipt in {benchmark}/{stage}")
                if record["request_sha256"] != sha(wire):
                    raise ValueError("Mismatched transfer receipt")
                results[uid, arm, stage] = {**record, "answer": answer}
        return results
    return dispatch


def evaluate(benchmark, source, dispatch):
    panel, archive, draft_jobs, reused = source
    counts = Counter()
    drafts = dict(reused)
    receipts = transfer.cached_dispatch(dispatch, draft_jobs, {}, (), counts)
    for (uid, _, _), record in receipts.items():
        if record["status"] == "OK" and record.get("answer"):
            drafts[uid] = {"answer": record["answer"], "sha256": record["request_sha256"], "receipt": record}
    answers, traces = generate(panel, drafts, lambda jobs: transfer.cached_dispatch(dispatch, jobs, {}, (), counts))
    missing = {r["uid"] for r in panel} - drafts.keys()
    for uid in sorted(missing):
        status = receipts.get((uid, transfer.TASK_ONLY, transfer.DRAFT), {}).get("status", "ARCHIVED_DRAFT_UNAVAILABLE")
        answers.extend({"uid": uid, "method": arm, "actor_status": "NO_USABLE_DRAFT",
                        "draft_status": status, "score": None, "answer": None}
                       for arm in core.method.MODES)
    # Author references and scoring policy are read after generation has returned.
    cases, protocol, controls = transfer.context(benchmark)
    if cases.keys() != {r["uid"] for r in panel}:
        raise ValueError("Transfer scorer differs from the exposed roster")
    cache, conflicts = transfer.matching_grading_receipts(benchmark, cases, protocol, archive)
    if benchmark == "BenchPreS":
        for root in panel:
            uid = root["uid"]
            draft = drafts.get(uid)
            answers.append({"uid": uid, "method": transfer.TASK_ONLY, "actor_status": "OK" if draft else "NO_USABLE_DRAFT",
                            "answer": draft["answer"] if draft else None, "score": None})
        pair = transfer.bench_pair
    else:
        pair = transfer.persist_pair
    transfer.grade(benchmark, answers, cases, protocol,
                   lambda jobs: transfer.cached_dispatch(dispatch, jobs, cache, conflicts, counts))
    cells = {(row["uid"], row["method"]): row["score"] for row in (*answers, *controls) if row["score"] is not None}
    others = {r["method"] for r in (*answers, *controls)} - {core.method.SCOPED}
    compared = {other: pair(other, core.method.SCOPED, cases, cells) for other in sorted(others)}
    return {"assigned": len(panel), "available_drafts": len(drafts), "reused_drafts": len(reused),
            "draft_locations_missing": sorted(missing), "grading_model": protocol["model"],
            "independent_confirmation": False, "rows": answers, "edit_traces": traces,
            "comparisons": compared, "cache": counts,
            "valid_by_arm": Counter(row["method"] for row in answers if row["score"] is not None)}


def execute(plan, inputs, benchmark, *, live):
    if live and probe.read_reference()[1] != plan["service_reference_sha256"]:
        raise ValueError("Transfer gateway fingerprint changed")
    probe.OUT, probe.RUN = OUT / benchmark, RUN / benchmark
    state = probe.OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING"})
    try:
        result = evaluate(benchmark, inputs[benchmark], stage_dispatch(plan, benchmark, live=live))
        caps = plan["panels"][benchmark]["caps"]
        records = [record for stage in caps for record, _ in probe.stage_receipts(stage).values()]
        if not records or any(r is None for r in records):
            raise ValueError("Expected terminal physical requests")
        keys = {(r["unit"]["stage"], r["request_sha256"]) for r in records}
        if len(keys) != len(records):
            raise ValueError("Transfer issued duplicate physical requests")
        result["ledger"] = records
        result["usage"] = {stage: usage([r for r in records if r["unit"]["stage"] == stage]) for stage in caps}
        probe.freeze(probe.OUT / "SETTLED.json", result)
    except (ValueError, OSError, RuntimeError) as error:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "requests": len(records)})


def verify_replay(plan, inputs, benchmark):
    state = read(OUT / benchmark / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("Transfer has not yet settled")
    files = []

    def match(path, rebuilt):
        if read(path) != json.loads(json.dumps(rebuilt)):
            raise ValueError(f"Transfer replay changed {path.name}")
        files.append(path.name)

    with patch.object(probe, "freeze", match):
        execute(plan, inputs, benchmark, live=False)
    if len(read(OUT / benchmark / "SETTLED.json")["ledger"]) != state["requests"]:
        raise ValueError("Transfer state and physical request ledger differ")
    print(json.dumps({"verified_files": files, "physical_requests": state["requests"], "new_model_requests": 0}))


def check_pipeline(plan, inputs, benchmark):
    panel, archive, _, reused = inputs[benchmark]
    fixture_drafts = {r["uid"]: r["answer"] for r in archive if r["method"] == transfer.RP and r["actor_status"] == "OK"}
    exchanged = Counter()

    def mock(jobs):
        outputs = {}
        for (uid, arm, stage), wire in jobs.items():
            exchanged[stage] += 1
            assert token_estimate(canonical(wire["messages"])) <= 32768
            if stage == transfer.DRAFT:
                payload = json.loads(wire["messages"][1]["content"])
                assert not payload["source_evidence"] and not payload["preference_use_policy"]
                body = fixture_drafts[uid]
            elif stage == core.STAGE:
                payload = json.loads(wire["messages"][1]["content"])
                if arm == core.method.ORDINARY:
                    body = json.dumps({"answer": payload["draft"]["D1"]["lines"][0]}, ensure_ascii=False)
                else:
                    body = '{"effects":[],"edits":[]}'
            else:
                body = None
            outputs[uid, arm, stage] = {"status": "OK" if body else "OFFLINE_GRADE_MISS",
                                         "request_sha256": sha(wire), "answer": body}
        return outputs

    result = evaluate(benchmark, inputs[benchmark], mock)
    expected = len(reused) if benchmark == "PersistBench" else len(panel)
    assert result["available_drafts"] == expected
    assert result["assigned"] == len(panel) and result["reused_drafts"] == len(reused)
    assert exchanged[core.STAGE] <= 2 * expected
    assert all(count <= plan["panels"][benchmark]["caps"][stage] for stage, count in exchanged.items())
    assert all(result["valid_by_arm"][arm] == (50 if benchmark == "PersistBench" else 46)
               for arm in core.method.MODES)
    return {"simulated_stage_positions": exchanged,
            "checked_pairwise_controls": sorted(result["comparisons"]), "new_model_requests": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "verify"))
    parser.add_argument("benchmark", choices=transfer.PANELS, nargs="?")
    args = parser.parse_args()
    plan, inputs = prepare()
    if args.action in ("check", "freeze"):
        print(json.dumps({name: {**verify(name), "request_caps": plan["panels"][name]["caps"],
                                 "end_to_end": check_pipeline(plan, inputs, name)}
                          for name in transfer.PANELS}, ensure_ascii=False, indent=2))
        if args.action == "freeze":
            probe.freeze(OUT / "FROZEN.json", plan)
    else:
        if args.benchmark is None:
            parser.error("run and verify require a benchmark")
        if plan != read(OUT / "FROZEN.json"):
            raise ValueError("Transfer differs from the frozen experiment")
        with probe.runner_lock(RUN / "runner.lock"):
            if args.action == "run":
                execute(plan, inputs, args.benchmark, live=True)
            else:
                verify_replay(plan, inputs, args.benchmark)
