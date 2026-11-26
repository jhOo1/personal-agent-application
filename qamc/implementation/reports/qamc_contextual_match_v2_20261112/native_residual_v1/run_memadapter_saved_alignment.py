"""Apply the common PersistBench scorer to archived full MemAdapter answers."""
import argparse
import json

from build_jobs import archive as baseline_archive
from freeze_persist_performance_panel import CONTROLS, HERE, read
from qamc.common import sha
from transfer_execution import grading_jobs
from transfer_replay import RUNS, persist, saved_scores
from trial_reassembly import engine, probe

OUT = HERE / "persist_memadapter_alignment_v1"
RUN = engine.RUN.with_name(OUT.name)
METHOD = "MEMADAPTER_FULL"
BENCH = "PersistBench"


def prepare():
    plan = read(CONTROLS / "PLAN.json")
    if plan["not_confirmation"] is not True or any(row["role"] != "DEV" for row in plan["cases"]):
        raise ValueError("Expected the exposed author-control panel")
    cases = {row["uid"]: row for row in plan["cases"]}
    originals = read(HERE.parent / "paper_baseline_validation_156_v1" / "RESULT_ROWS.json")
    rubric = {}
    for file in sorted((CONTROLS / "waves").glob("[0-9][0-9].json")):
        for row in read(file)["rows"]:
            if row["uid"] in cases and row["method"] == "PB_RUBRIC" and row["score"] is not None:
                if row["uid"] in rubric:
                    raise ValueError("Ambiguous rubric baseline")
                rubric[row["uid"]] = row
    _, protocol, _ = baseline_archive.transfer.context(BENCH)
    receipts = saved_scores(RUNS / persist.AUTHOR_OUT.name / "gpt41")
    manifest, rows = [], []
    for original in originals:
        uid = original["uid"]
        if uid not in cases or original["method"] != METHOD:
            continue
        case = cases[uid]
        base = rubric.get(uid)
        row = {"uid": uid, "benchmark": BENCH, "method": METHOD, "group": case["group_id"],
               "category": case["category"], "base_score": base["score"] if base else None,
               "actor_status": original["actor_status"], "answer": original.get("answer"), "score": None}
        if base is not None:
            wire, = grading_jobs(BENCH, [base], cases, protocol)[0].values()
            receipt = receipts[uid, "PB_RUBRIC"]
            if sha(wire) != receipt["request_sha256"] or base["raw_scores"][persist.STAGE] != receipt["response"]["answer"]:
                raise ValueError(f"Archived Judge drift: {uid}")
        grade_hash = None
        if row["actor_status"] == "OK":
            if sha(original["actor_request"]) != original["actor_request_sha256"] or not row["answer"]:
                raise ValueError(f"Archived Actor drift: {uid}")
            wire, = grading_jobs(BENCH, [row], cases, protocol)[0].values()
            grade_hash = sha(wire)
        manifest.append({"uid": uid, "actor_status": row["actor_status"], "grade_sha256": grade_hash,
                         "answer_sha256": sha(row["answer"]) if row["answer"] else None})
        rows.append(row)
    if len(rows) != len(cases) or {row["uid"] for row in rows} != set(cases):
        raise ValueError("Archived MemAdapter coverage differs from the frozen cohort")
    return manifest, rows, cases, protocol


def run():
    manifest, rows, cases, protocol = prepare()
    caps = {"PersistNative": sum(row["grade_sha256"] is not None for row in manifest)}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([manifest, caps, sha((HERE / "run_memadapter_saved_alignment.py").read_bytes())])}
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)
        probe.freeze(OUT / "INPUTS.json", manifest)

        def dispatch(jobs):
            if not jobs:
                return {}
            expected = {card["uid"]: card["grade_sha256"] for card in manifest}
            for (uid, _, _), wire in jobs.items():
                if sha(wire) != expected[uid]:
                    raise ValueError(f"Live scorer differs from frozen request: {uid}")
            results = engine.stage("PersistNative", {(uid, f"{method}/{field}"): wire
                                                   for (uid, method, field), wire in jobs.items()},
                                   identity, True, ledger)
            return {(uid, method, field): results[uid, f"{method}/{field}"]
                    for uid, method, field in jobs}

        baseline_archive.transfer.grade(BENCH, rows, cases, protocol, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    if parser.parse_args().action == "check":
        cards, rows, _, _ = prepare()
        print(json.dumps({"allocated": len(rows), "gradable": sum(c["grade_sha256"] is not None for c in cards),
                          "paired_expected": sum(r["base_score"] is not None and r["actor_status"] == "OK" for r in rows)}))
    else:
        run()
