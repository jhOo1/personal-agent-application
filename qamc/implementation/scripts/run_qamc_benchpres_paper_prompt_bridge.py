"""Run the paper's selectivity prompt on archived Style/GP0 development pairs."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

import pyarrow.parquet as parquet

import run_qamc_benchpres_fact_projection as bench
import freeze_qamc_benchpres_new_pairs as previous
from proposals.qamc_benchpres_mitigation.engine import DEFENSE

base, ROOT = bench.base, bench.ROOT
read, frozen, sha = bench.read, bench.frozen, bench.sha
NAME = "qamc_benchpres_paper_prompt_bridge"
OUT, RUN = ROOT / "reports" / NAME, ROOT / "runs" / NAME
METHOD = "PAPER_SELECTIVITY"
CAP = 70
MARKER = "\nOnly output the message that would be sent to "
PROFILE_END = "\n\nWrite a complete message to recipient"
JUDGES = bench.JUDGES


def render(prompt, defense):
    profile, query = prompt.split(PROFILE_END)
    if not profile.strip() or query.count(MARKER) != 1:
        raise ValueError("Unrecognized official prompt")
    return profile + PROFILE_END + query.replace(MARKER, "\n" + defense + MARKER, 1)


def check(plan):
    assert len(plan["cases"]) == len({c["profile_group"] for c in plan["cases"]}) == 10
    assert len(plan["initial"]) == 10 and len(set(plan["allowed_unit_keys"])) == CAP
    assert all(base.file_sha(ROOT / p) == h for p, h in plan["files"].items())


def prepare():
    old_path = previous.OUT / "PLAN.json"
    old = read(old_path)
    source = next(p for p in (ROOT / old["source"], ROOT.with_name("qamc") / old["source"]) if p.is_file())
    assert base.file_sha(source) == old["source_sha256"]
    prompts = parquet.read_table(source, columns=["prompt"]).column(0)
    assert len(prompts) == 390
    protocol = {**old["protocol"], "namespace": NAME,
                "stages": {s: old["protocol"]["stages"][s] for s in ("Actor", *JUDGES)}}
    profiles = defaultdict(list)
    for c in old["cases"]:
        profiles[c["profile_group"]].append(c)
    assert len(profiles) == 10 and all(len(p) == 2 for p in profiles.values())
    chosen = [min(rows, key=lambda c: sha([NAME, c["uid"]])) for rows in profiles.values()]
    plan = {"protocol": protocol, "cases": chosen, "initial": [], "source_sha256": old["source_sha256"]}
    defense = DEFENSE.read_text().strip()
    files = [Path(__file__), DEFENSE, OUT / "RULES.md", old_path, previous.OUT / "PILOT.json",
             ROOT / "proposals/qamc_memgate_external/evaluation.py", ROOT / "src/qamc/pilot_scoring.py"]
    for c in chosen:
        uid = c["uid"]
        original = prompts[c["row_index"]].as_py()
        assert previous.benchpres_public(original, uid).query == read(ROOT / c["public_path"])["query"]
        body = render(original, defense)
        assert body.replace("\n" + defense, "", 1) == original
        plan["initial"].append(base.job(plan, uid, METHOD, "Actor", [{"role": "user", "content": body}]))
        files.extend(ROOT / c[k] for k in ("public_path", "evaluation_path"))
    plan["allowed_unit_keys"] = sorted(base.sampling_key(base.unit(plan, c["uid"], METHOD, s))
                                      for c in chosen for s in ("Actor", *JUDGES))
    plan["files"] = {str(p.relative_to(ROOT)): base.file_sha(p) for p in files}
    check(plan)
    frozen(OUT / "PLAN.json", plan)


def collect(plan, runtime):
    rows, jobs = [], []
    for c, job in zip(plan["cases"], plan["initial"], strict=True):
        uid = c["uid"]
        actor = runtime.output(job["unit"])
        row = {"uid": uid, "actor_status": actor["status"] if actor else "NOT_RUN", "score": None}
        rows.append(row)
        if row["actor_status"] != "OK":
            continue
        assert actor["request_sha256"] == sha(job["request"])
        ref = read(ROOT / c["evaluation_path"])
        assert bench.digest(ref) == c["evaluation_hash"]
        answer = row["answer"] = actor["response"]["answer"]
        query = read(ROOT / c["public_path"])["query"]
        raws, statuses = {}, {}
        for stage, system, payload in bench.initial_requests(ROOT, "benchpres", ref, query, answer):
            judge_job = bench.job(plan, uid, METHOD, stage, system, payload)
            jobs.append(judge_job)
            saved = runtime.output(judge_job["unit"])
            statuses[stage] = saved["status"] if saved else "NOT_RUN"
            if saved and saved["status"] == "OK":
                assert saved["request_sha256"] == sha(judge_job["request"])
                raws[stage] = saved["response"]["answer"]
        row.update(judge_answers=raws, judge_statuses=statuses)
        if set(raws) == set(JUDGES):
            try:
                row["score"] = bench.grade(ROOT, "benchpres", ref, raws)
            except (TypeError, ValueError, KeyError) as exc:
                row["score_error"] = str(exc)
    return rows, jobs


def summary(plan, rows):
    by = {row["uid"]: {METHOD: row["score"]} for row in rows}
    for r in read(previous.OUT / "PILOT.json")["rows"]:
        if r["uid"] in by and r["method"] in ("STYLE", "GP0"):
            by[r["uid"]][r["method"]] = r["score"]
    common = [uid for uid, arms in by.items() if all(arms.values())]
    comparisons = {}
    for scope, methods in (("all_common", ("STYLE", "GP0", METHOD)),
                           ("style_pair", ("STYLE", METHOD)), ("gp0_pair", ("GP0", METHOD))):
        uids = [uid for uid, scores in by.items() if all(scores[m] is not None for m in methods)]
        out = {"uids": uids, "metrics": {}, "appropriate": {}}
        for method in methods:
            scores = [by[uid][method] for uid in uids]
            out["metrics"][method] = bench.aggregate_bench(scores)
            split = defaultdict(Counter)
            for score in scores:
                for decision in score["decisions"]:
                    if decision["appropriate"]:
                        category = "bold" if re.search(r"\bbold text\b", decision["preference"], re.I) else "other"
                        split[category]["total"] += 1
                        split[category]["followed"] += decision["label"] == "follow"
            out["appropriate"][method] = dict(split)
        comparisons[scope] = out
    assert comparisons["all_common"]["uids"] == common
    fields = ("aar_numerator", "mr_numerator", "task_completeness")
    comparisons["by_case"] = {uid: {m: {k: s[k] for k in fields} if s else None for m, s in by[uid].items()}
                              for uid in by}
    return comparisons


def stage(plan, rt, name, jobs):
    if not jobs:
        return
    path = OUT / f"{name}_CACHE.json"
    index = read(path) if path.exists() else base.caches.inventory(jobs)
    assert index["wanted"] == sorted({sha(j["request"]) for j in jobs})
    frozen(path, index)
    rt.stage(plan, "pilot", name, jobs, index)


def main(action):
    if action == "prepare":
        prepare()
        return
    plan = read(OUT / "PLAN.json")
    check(plan)
    rt = base.rtlib.Runtime(ROOT.parent, OUT, RUN, check)
    if action == "run":
        RUN.mkdir(parents=True, exist_ok=True)
        with base.caches.old.runner_lock(RUN / "runner.lock"):
            stop = RUN / "STOP"
            if stop.exists():
                raise ValueError("Trial already terminal")
            base.rtlib.exact = base.caches.old.prefilter_exact
            stage(plan, rt, "Smoke", plan["initial"][:1])
            smoke = rt.output(plan["initial"][0]["unit"])
            if smoke["status"] == "OK":
                stage(plan, rt, "Actor", plan["initial"][1:])
                stage(plan, rt, "Judge", collect(plan, rt)[1])
            rows, _ = collect(plan, rt)
            ledger = base.caches.old.snapshot(RUN, CAP)
            assert not ledger["in_flight_observations"]
            frozen(OUT / "PILOT.json", {"rows": rows, "summary": summary(plan, rows), "ledger": ledger})
            stop.write_text("Paper prompt bridge terminal.\n")
    elif action == "report":
        saved = read(OUT / "PILOT.json")
        rows, _ = collect(plan, rt)
        assert rows == saved["rows"] and summary(plan, rows) == saved["summary"]
        assert base.caches.old.snapshot(RUN, CAP) == saved["ledger"]
        print(json.dumps(saved["summary"], ensure_ascii=False))
    else:
        raise ValueError("Use prepare, run or report")


if __name__ == "__main__":
    main(sys.argv[1])
