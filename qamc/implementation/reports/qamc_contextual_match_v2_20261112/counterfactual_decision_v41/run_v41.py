"""Freeze, dispatch and replay the shared-input RPEval V41 comparison."""
from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

from qamc.common import parse_object, sha
from intervention import REVIEW_INSTRUCTIONS, final_requests, parse_final, task_only_request

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent
sys.path.insert(0, str(REPORTS / "gate_shared_proposal_review_v9"))
import run_review as baseline
from cohort import receipt

probe, formal, read = baseline.probe, baseline.formal, baseline.read
RP, GATE, NATIVE = baseline.RP, baseline.GATE, baseline.NATIVE
ARMS = tuple(REVIEW_INSTRUCTIONS)
DRAFT, FINAL = "TaskDraft", "FinalReview"
STAGES = (DRAFT, FINAL, NATIVE)
OUT = REPORTS / "counterfactual_rpeval_v41"
RUN = formal.RUN.parent / OUT.name
WIDE = formal.ROOT / "runs/qamc_scale_review_20261118/FIXED_POLICY_PUBLIC_INPUTS_233.json"
NARROW = REPORTS / "scale_review_20261118/FIXED_POLICY_PUBLIC_INPUTS.json"
CAP = {DRAFT: 233, FINAL: 466, NATIVE: 466}
BATCH_SIZE = 32

baseline.ARMS = ARMS


def pin():
    paths = (Path(__file__), HERE / "intervention.py", HERE / "analyze.py", HERE / "EXECUTION.md",
             WIDE, NARROW)
    return {path.name: sha(path.read_bytes()) for path in paths}


def author_cases(parent):
    return {row["uid"]: row for row in parent["cases"] if row["independent_confirmation"] is False}


def archived_answer(parent, case, row, inherited):
    uid, method = case["uid"], row["method"]
    request, answer = row["actor_request"], row["answer"]
    if row["actor_status"] != "OK" or not answer or sha(request) != row["actor_request_sha256"]:
        raise ValueError(f"Unverified archived Actor request for {uid}, {method}")
    if row.get("generation_origin") == "EXACT_FIXED_LEGACY_TRAJECTORY":
        witness = inherited[uid, method]
        if (witness["actor_request"], witness["answer"]) != (request, answer):
            raise ValueError(f"Legacy replay mismatch for {uid}, {method}")
    else:
        witness = receipt(parent, uid, method, "Actor")
        if not witness or (witness["request_sha256"], witness["response"]["answer"]) != (sha(request), answer):
            raise ValueError(f"Actor receipt mismatch for {uid}, {method}")
    raw = (row.get("raw_scores") or {}).get(NATIVE)
    if raw is not None:
        request_item, = formal.grading_jobs(parent, [case], [row])
        score = receipt(parent, uid, method, NATIVE)
        if not score or (score["request_sha256"], score["response"]["answer"]) != (sha(request_item["request"]), raw):
            raise ValueError(f"Native grading receipt mismatch for {uid}, {method}")
    return {"answer": answer, "fields": row.get("native_fields") or {}, "raw_judge": raw,
            "actor_sha256": sha(request)}


def ordered_waves(roots):
    by_group = {}
    for root in sorted(roots, key=lambda row: sha(["v41-smoke-group", row["group"], row["uid"]])):
        by_group.setdefault(root["group"], root["uid"])
    smoke = set(list(by_group.values())[:4])
    remaining = [row["uid"] for row in roots if row["uid"] not in smoke]
    return [sorted(smoke), *[remaining[i:i + BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]]


def prepare():
    roots = read(WIDE)["roots"]
    uids = {root["uid"] for root in roots}
    narrow = {root["uid"] for root in read(NARROW)["roots"]}
    parent = read(formal.OUT / "PLAN.json")
    exposed = author_cases(parent)
    if (len(roots) != 233 or len(uids) != 233 or len({r["source_group"] for r in roots}) != 43
            or len(narrow) != 118 or not narrow <= uids <= exposed.keys()):
        raise ValueError("V41 panel changed")
    archives = {(row["uid"], row["method"]): row for row in read(formal.OUT / "RESULT_ROWS.json")
                if row["uid"] in uids and row["method"] in (RP, GATE)}
    inherited = {(row["uid"], row["method"]): row for row in
                 read(formal.OUT / "INHERITED_GENERATION_ROWS.json")
                 if row["uid"] in uids and row["method"] in (RP, GATE)}
    formal.replay_inherited(list(inherited.values()), list(exposed.values()))
    assembled = []
    for root in roots:
        uid = root["uid"]
        archived = {m: archived_answer(parent, exposed[uid], archives[uid, m], inherited)
                    for m in (RP, GATE)}
        if archived[RP]["actor_sha256"] != root["archived_actor_sha256"]:
            raise ValueError(f"RP archive changed for {uid}")
        task_wire = task_only_request(root)
        assembled.append({**root, "group": root["source_group"], "in_sensitivity": uid in narrow,
                          "archived": archived, "task_wire_sha256": sha(task_wire)})
    return {"roots": assembled, "waves": ordered_waves(assembled), "pin": pin(), "cap": CAP,
            "independent_confirmation": False, "service_reference_sha256": parent["service_reference_sha256"]}


def manifest(wave, stage, jobs):
    model, cap = ("gpt-4.1", 8192) if stage == NATIVE else ("qwen3.8-flash", 4096)
    protocol = {"experiment": f"{OUT.name}/{wave}", "model": model, "concurrency": 8,
                "spacing_seconds": 3.2, "stages": {stage: {"max_tokens": cap, "temperature": 0}},
                "automatic_retries": 0}
    return {"protocol": protocol, "units": [
        {"unit": {"stage": stage, "root_id": uid, "method": arm, "replicate": 0,
                  "protocol_sha256": sha(protocol)}, "request": request}
        for uid, arm, request in jobs
    ]}


def dispatch(plan, stage, frozen):
    if not frozen["units"]:
        return
    sampler = probe.UsageObservableSampler(probe.RUN / stage, frozen)
    try:
        if sampler.reference_sha != plan["service_reference_sha256"]:
            raise ValueError("Gateway fingerprint changed")
        probe.cooldown_minute(sampler.control)

        def work(job):
            with sampler.control.lock:
                stop, = sampler.control.db.execute("SELECT hard_stop FROM dispatch WHERE id=1").fetchone()
            if stop or (sampler.root / "STOP").exists():
                return "STOP_NO_DISPATCH"
            try:
                result = sampler.perform(job["unit"], job["request"])
            except RuntimeError as error:
                return str(error)
            return "CACHE" if result["cache_hit"] else "OK"

        with ThreadPoolExecutor(max_workers=8) as pool:
            for job, status in zip(frozen["units"], pool.map(work, frozen["units"]), strict=True):
                print(stage, job["unit"]["root_id"], job["unit"]["method"], status, flush=True)
        with sampler.control.lock:
            stop, = sampler.control.db.execute("SELECT hard_stop FROM dispatch WHERE id=1").fetchone()
        if stop or (sampler.root / "STOP").exists():
            raise RuntimeError(f"Retained transport stop in {stage}; later stages were not started")
    finally:
        sampler.close()


def stage(plan, wave, name, jobs, live):
    exact = {}
    if name != DRAFT:
        for previous in sorted(OUT.glob("wave_*")):
            if previous.name >= wave:
                break
            path = previous / (name + "_EXACT.json")
            if path.exists():
                exact.update(read(path))
    unique, index = {}, {}
    for uid, arm, wire in jobs:
        digest = sha(wire)
        index[uid, arm] = digest
        if digest not in exact:
            unique.setdefault(digest, (uid, arm, wire))
    frozen = manifest(wave, name, list(unique.values()))
    probe.freeze(probe.OUT / (name + "_MANIFEST.json"), frozen)
    if live:
        dispatch(plan, name, frozen)
    received = probe.stage_receipts(name)
    local = {digest: received[uid, arm] for digest, (uid, arm, _) in unique.items()}
    # JSON round-tripping results normalizes the same tuple/list representation.
    if name != DRAFT:
        probe.freeze(probe.OUT / (name + "_EXACT.json"),
                     {digest: list(result) for digest, result in local.items()})
        probe.freeze(probe.OUT / (name + "_WIRE_REUSE.json"), [
            {"uid": uid, "arm": arm, "sha256": digest}
            for (uid, arm), digest in index.items()
            if digest in exact or unique[digest][:2] != (uid, arm)
        ])
    return {(uid, arm): (exact[digest] if digest in exact else local[digest])
            for (uid, arm), digest in index.items()}


def shared_drafts(plan, wave, past_drafts, live):
    jobs, digest_index, aliases = [], {}, {}
    for root in plan["roots"]:
        uid = root["uid"]
        wire = task_only_request(root)
        digest = sha(wire)
        if digest != root["task_wire_sha256"]:
            raise ValueError("Frozen draft request changed")
        if digest in past_drafts:
            aliases[uid] = past_drafts[digest]["uid"]
        elif digest in digest_index:
            aliases[uid] = digest_index[digest]
        else:
            digest_index[digest] = uid
            jobs.append((uid, "SHARED", wire))
    probe.freeze(probe.OUT / "DRAFT_REUSE.json", aliases)
    responses = stage(plan, wave, DRAFT, jobs, live)
    produced = {digest: {"uid": uid, "record": responses[uid, "SHARED"][0],
                         "answer": responses[uid, "SHARED"][1]}
                for digest, uid in digest_index.items()}
    probe.freeze(probe.OUT / "DRAFT_RESULTS.json", produced)
    return {**past_drafts, **produced}, aliases


def evaluate(plan, wave, past_drafts, live):
    roots = plan["roots"]
    drafts, aliases = shared_drafts(plan, wave, past_drafts, live)
    trace, final_jobs = {}, []
    for root in roots:
        uid = root["uid"]
        value = drafts[root["task_wire_sha256"]]
        record, answer = value["record"], value["answer"]
        state = trace[uid] = {"draft_status": record["status"] if record else "UNISSUED"}
        if uid in aliases:
            state["draft_reused_from"] = aliases[uid]
        if answer:
            state["draft_sha256"] = sha(answer)
            wires = final_requests(root, archived_draft=root["archived"][RP]["answer"], task_only_draft=answer)
            state["review_sha256"] = {arm: sha(wire) for arm, wire in wires.items()}
            final_jobs.extend((uid, arm, wire) for arm, wire in wires.items())
    finals = stage(plan, wave, FINAL, final_jobs, live)
    answers = {}
    for root in roots:
        uid = root["uid"]
        answers[uid] = {}
        for arm in ARMS:
            record, raw = finals.get((uid, arm), (None, None))
            entry = {"status": record["status"] if record else "NO_USABLE_DRAFT" if
                     (uid, arm) not in finals else "UNISSUED", "answer": None}
            if raw:
                try:
                    entry.update(parse_final(raw, root))
                except (ValueError, TypeError) as error:
                    entry.update(status="INVALID_FINAL_CONTRACT", error=str(error))
            answers[uid][arm] = entry
    probe.freeze(probe.OUT / "ANSWERS.json", answers)
    jobs, aliases = baseline.grade_jobs(plan, answers)
    probe.freeze(probe.OUT / "GRADE_REUSE.json", aliases)
    grades = stage(plan, wave, NATIVE, jobs, live)
    rows = []
    for root in roots:
        uid = root["uid"]
        scored = {m: {"fields": val["fields"], "raw": val["raw_judge"]} for m, val in root["archived"].items()}
        for arm in ARMS:
            alias = aliases[uid].get(arm)
            if alias is not None:
                scored[arm] = {**scored[alias], "reuse": alias}
                continue
            record, raw = grades.get((uid, arm), (None, None))
            entry = scored[arm] = {"fields": {}, "raw": raw, "status": record["status"] if record else "UNISSUED"}
            if raw:
                try:
                    entry["fields"], entry["invalid"] = probe.fields(parse_object(raw), len(root["archived_policy"]), True)
                except (ValueError, KeyError, TypeError) as error:
                    entry["invalid"] = str(error)
        rows.append({"uid": uid, "group": root["group"], "in_sensitivity": root["in_sensitivity"],
                     "native": scored, "answers": answers[uid], "trace": trace[uid]})
    receipts = [{**rec, "wave": wave, "stage": name} for name in STAGES
                for rec, _ in probe.stage_receipts(name).values() if rec]
    probe.freeze(probe.OUT / "COMPLETED.json", {"rows": rows, "ledger": receipts})
    return rows


def smoke_check(rows):
    paired_answers = sum(all(row["answers"][arm]["answer"] for arm in ARMS) for row in rows)
    paired_scores = sum(all("match" in row["native"][arm]["fields"] for arm in ARMS) for row in rows)
    return {"paired_answer_contracts": paired_answers, "paired_native_contracts": paired_scores,
            "pass": paired_answers >= 3 and paired_scores >= 2}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "smoke", "run"))
    phase = parser.parse_args().phase
    frozen = OUT / "FROZEN.json"
    with probe.runner_lock(RUN / "runner.lock"):
        if phase == "freeze":
            probe.freeze(frozen, prepare())
            print(f"Frozen 233 exposed tasks across 43 groups, at most {sum(CAP.values())} primary requests.")
            return
        plan = read(frozen)
        if plan["pin"] != pin() or plan["cap"] != CAP or plan["independent_confirmation"] is not False:
            raise ValueError("V41 execution contract changed")
        if probe.read_reference()[1] != plan["service_reference_sha256"]:
            raise ValueError("Gateway reference changed")
        by_uid = {r["uid"]: r for r in plan["roots"]}
        prior_drafts = {}
        for index, uids in enumerate(plan["waves"][:1] if phase == "smoke" else plan["waves"]):
            wave = f"wave_{index:02d}"
            probe.OUT, probe.RUN = OUT / wave, RUN / wave
            finished = probe.OUT / "COMPLETED.json"
            probe.atomic_json(OUT / "RUN_STATE.json", {"state": "RUNNING", "phase": phase, "wave": wave})
            try:
                if finished.exists():
                    rows = read(finished)["rows"]
                else:
                    rows = evaluate({**plan, "roots": [by_uid[uid] for uid in uids]}, wave, prior_drafts, live=True)
                prior_drafts.update(read(probe.OUT / "DRAFT_RESULTS.json"))
                if index == 0:
                    decision = smoke_check(rows)
                    probe.freeze(OUT / "SMOKE.json", decision)
                    print("SMOKE", decision, flush=True)
                    if not decision["pass"]:
                        raise RuntimeError("Smoke contract failed")
            except (ValueError, RuntimeError) as error:
                probe.atomic_json(OUT / "RUN_STATE.json", {"state": "STOPPED", "phase": phase,
                                                         "wave": wave, "error": str(error)})
                raise
        probe.atomic_json(OUT / "RUN_STATE.json", {"state": "COMPLETE", "phase": phase,
                                                 "waves": index + 1})
        print(f"V41 {phase} complete.", flush=True)


if __name__ == "__main__":
    main()
