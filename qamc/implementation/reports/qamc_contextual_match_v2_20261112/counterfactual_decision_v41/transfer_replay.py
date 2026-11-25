"""Check whether the unchanged V41 contract and strong controls transfer without new calls."""
from collections import Counter
from dataclasses import asdict
import json

from qamc.common import sha
import qamc_paper_baseline_validation_run as development
import qamc_benchpres_matched_paper_run as bench
import qamc_persist_saved_answer_alignment_run as persist
from intervention import final_requests, task_only_request

ROOT = development.ROOT
REPORTS = development.OUT.parent
RUNS = ROOT / "runs" / REPORTS.name
RP = "RPR_PAPER_FULL"
GATE = "GEPA_SELECTED_BOUNDS"
C5 = "GOAL_EFFECT_GEPA"
BENCH_CONTROLS = (RP, GATE, C5, bench.METHOD)
PERSIST_CONTROLS = ("PB_RUBRIC", "PB_GEPA", "PB_NO_MEMORY")
STAGE = persist.STAGE


def read(path):
    return json.loads(path.read_text())


def replay_actor(task, row, original_systems):
    view = row["view"]
    public = {"query": task.query, "current_context": task.current_context, "facts": list(task.fixed_facts)}
    sources = [{"memory_id": memory.memory_id, "text": memory.text} for memory in task.memories]
    actor = row["actor_request"]
    policy = view["preference_use_policy"]
    if (view != {**public, "source_evidence": sources, "preference_use_policy": policy}
            or [entry["memory_id"] for entry in policy] != [src["memory_id"] for src in sources]
            or any(entry["policy"] not in {"A", "B", "C"} for entry in policy)
            or actor["messages"][0]["content"] not in original_systems
            or (actor["model"], actor["temperature"], actor["max_tokens"]) != ("qwen3.8-flash", 0, 4096)):
        raise ValueError(f"Transferred RP anchor differs from frozen protocol: {task.uid}")
    root = {"archived_actor_request": actor, "archived_actor_sha256": row["actor_request_sha256"],
            "public_task": public, "original_sources": sources, "archived_policy": policy}
    task_wire = task_only_request(root)
    placeholder = "Contract check only. This text is never sent to a model."
    finals = final_requests(root, archived_draft=row["answer"], task_only_draft=placeholder)
    if finals["DELTA"]["messages"][1] != finals["REVIEW"]["messages"][1]:
        raise ValueError("Transfer lost shared-input parity")
    return {"actor_sha256": sha(actor), "archived_answer_sha256": sha(row["answer"]),
            "task_draft_sha256": sha(task_wire), "memory_count": len(sources)}


def saved_scores(run_folder):
    valid = {}
    for path in sorted(run_folder.glob("outputs/*.json")):
        cell = read(path)
        if cell["status"] == "OK" and cell["unit"]["stage"] == STAGE:
            valid[cell["unit"]["root_id"], cell["unit"]["method"]] = cell
    return valid


def persist_replay(tasks, archive_rows):
    authors = persist.AUTHOR_OUT
    protocol = read(authors / "PLAN.json")["protocols"]["gpt41"]
    evaluator = persist.author.ext.parent.persist
    _, rubrics, fmt = evaluator.upstream()
    author_rows = {(row["uid"], row["method"]): row
                   for wave in sorted((authors / "waves").glob("*.json"))
                   for row in read(wave)["rows"] if row["method"] in PERSIST_CONTROLS}
    receipts = saved_scores(RUNS / authors.name / "gpt41")
    saved = saved_scores(persist.RUN / "grading")
    saved_by_digest = {record["request_sha256"]: record for record in saved.values()}
    exact_in_house, exact_author = set(), set()
    by_wire = {}

    def judge_request(uid, category, answer):
        task = tasks[uid]
        return persist.author.ext.text_request(
            rubrics[category], fmt["build_judge_prompt"]([m.text for m in task.memories], task.query, answer),
            protocol["model"], protocol["stages"][STAGE]["max_tokens"],
        )

    for (uid, method), row in author_rows.items():
        if row["score"] is None or uid not in tasks:
            continue
        category = row["score"]["category"]
        score_body = judge_request(uid, category, row["answer"])
        witness = receipts[uid, method]
        raw = row["raw_scores"][STAGE]
        if (sha(score_body) != witness["request_sha256"] or raw != witness["response"]["answer"]
                or any(row["score"][name] != value for name, value in evaluator.score(category, raw).items())):
            raise ValueError(f"Saved PersistBench author-control score changed: {uid}, {method}")
        exact_author.add((uid, method))
        by_wire.setdefault(sha(score_body), (uid, method))
    for result in read(persist.OUT / "RESULTS.json")["rows"]:
        uid, method = result["uid"], result["method"]
        if uid not in tasks or result["score"] is None:
            continue
        score_body = judge_request(uid, result["category"], archive_rows[uid, method]["answer"])
        digest = sha(score_body)
        record = saved_by_digest[digest]
        if digest != result["judge_request_sha256"] or digest != record["request_sha256"]:
            raise ValueError(f"Saved PersistBench in-house request changed: {uid}, {method}")
        if result["raw_judge"] != record["response"]["answer"]:
            raise ValueError(f"Saved PersistBench in-house response changed: {uid}, {method}")
        exact_in_house.add((uid, method))
        by_wire.setdefault(digest, (uid, method))

    cases = []
    for uid, task in tasks.items():
        row = archive_rows[uid, RP]
        if row["actor_status"] != "OK" or not row["answer"]:
            continue
        category = row["score"]["category"] if row["score"] is not None else None
        if category is None:
            raise ValueError("Missing category for saved RP draft")
        digest = sha(judge_request(uid, category, row["answer"]))
        eligible = [method for method in PERSIST_CONTROLS if (uid, method) in exact_author]
        cases.append({"uid": uid, "category": category,
                      "RP_gpt41_exact_cache": by_wire.get(digest), "RP_gpt41_request_sha256": digest,
                      "matched_author_controls": eligible,
                      "matched_in_house_controls": [method for method in (C5, GATE) if (uid, method) in exact_in_house]})
    return cases


def run():
    parent = read(development.OUT / "PLAN.json")
    bench_plan, persist_plan = (read(directory / "PLAN.json") for directory in (bench.OUT, persist.AUTHOR_OUT))
    bench_cases = {c["uid"]: c for c in bench_plan["cases"] if c["independent_confirmation"] is False}
    bench_uids = bench_cases.keys()
    persist_uids = {c["uid"] for c in persist_plan["cases"] if c["role"] == "DEV"}
    if len(bench_uids) != 48 or len(persist_uids) != 60:
        raise ValueError("Expected only the archived development endpoints")
    cases = {c["uid"]: c for c in parent["cases"] if c["uid"] in bench_uids | persist_uids}
    public = read(development.OUT / "PUBLIC_TASKS.json")
    observed = {(r["uid"], r["method"]): r for r in read(development.OUT / "RESULT_ROWS.json") if r["uid"] in cases}
    rpeval = read(REPORTS / "counterfactual_rpeval_v41/FROZEN.json")
    systems = {c["archived_actor_request"]["messages"][0]["content"] for c in rpeval["roots"]}
    tasks = {uid: development.task_for(case) for uid, case in cases.items()}
    compatibility = {}
    for uid, task in tasks.items():
        if uid != task.uid or sha(asdict(task)) != sha(public[uid]):
            raise ValueError(f"Public comparative job drift: {uid}")
        row = observed[uid, RP]
        if row["actor_status"] == "OK" and row["answer"]:
            compatibility[uid] = replay_actor(task, row, systems)
    match = read(bench.OUT / "RESULT_ROWS.json")
    paper = {r["uid"]: r for r in match}
    if paper.keys() != bench_uids:
        raise ValueError("BenchPreS same-configuration paper coverage changed")
    for stage, frozen in bench_plan["protocols"].items():
        planned = parent["protocols"][stage]
        if frozen["model"] != planned["model"] or any(
            settings != planned["stages"][name] for name, settings in frozen["stages"].items()
        ):
            raise ValueError("BenchPreS saved paper controls use different scoring or sampling settings")
    if read(bench.OUT / "TERMINAL_ACCEPTANCE.json")["status"] != "PASS":
        raise ValueError("BenchPreS archived controls failed acceptance")
    bcases = []
    for uid in sorted(bench_uids):
        obj = paper[uid]
        available = [m for m in BENCH_CONTROLS
                     if (obj if m == bench.METHOD else observed[uid, m])["score"] is not None]
        bcases.append({"uid": uid, "profile_group": bench_cases[uid]["analysis_group_id"], "matched_controls": available,
                       "actor_compatible": uid in compatibility})
    pcases = persist_replay({uid: tasks[uid] for uid in sorted(persist_uids)}, observed)
    return {
        "new_model_requests": 0, "dispatch_plan_created": False, "independent_confirmation": False,
        "benchpres": {"archived_roots": len(bench_uids), "compatible_RP_Actor": len(bench_uids & compatibility.keys()),
                      "profile_groups": len({row["profile_group"] for row in bcases}),
                      "control_coverage": Counter(m for row in bcases for m in row["matched_controls"]),
                      "all_four_controls": sum(set(row["matched_controls"]) == set(BENCH_CONTROLS) for row in bcases),
                      "cases": bcases},
        "persistbench": {"archived_roots": len(persist_uids), "compatible_RP_Actor": len(pcases),
                         "categories": Counter(row["category"] for row in pcases),
                         "RP_gpt41_exact_cache": sum(row["RP_gpt41_exact_cache"] is not None for row in pcases),
                         "gpt41_author_control_coverage": Counter(m for row in pcases for m in row["matched_author_controls"]),
                         "gpt41_in_house_control_coverage": Counter(m for row in pcases for m in row["matched_in_house_controls"]),
                         "cases": pcases},
        "verified_RP_sources_and_wires": compatibility,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
