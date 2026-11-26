"""Complete missing full-history controls beside exact cached selected answers."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import subprocess

from complete import engine, normalized, probe, read
from extension_inventory import prepare as inventory
from qamc.common import sha

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name("persist_historical_utility_completion_v1")
STAGES = ("FullActor", "FullNative")


def receipt(root, stage, uid, wire):
    path = root / stage / "samples.sqlite"
    with sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True) as db:
        matches = db.execute("SELECT unit_json, status, request_json, response_json FROM samples WHERE request_sha = ?",
                             (sha(wire),)).fetchall()
    matches = [x for x in matches if json.loads(x[0])["root_id"] == uid]
    if len(matches) != 1:
        raise ValueError(f"Historical {stage} receipt is ambiguous")
    _, status, actual_wire, response = matches[0]
    if status != "COMPLETE" or json.loads(actual_wire) != wire or not response:
        raise ValueError(f"Invalid historical {stage} receipt")
    return json.loads(response)["answer"]


def archived(wires, root):
    keys = {sha(wire): key for key, wire in wires.items()}
    if not keys:
        return {}, 0
    cmd = ["rg", "--files", "-g", "samples.sqlite", "-g", "!**/*seal*/**",
           "-g", "!**/*holdout*/**", "-g", "!**/*confirm*/**", "runs", "reports"]
    paths = subprocess.run(cmd, cwd=root, text=True, check=True, capture_output=True).stdout.splitlines()
    found = {}
    for name in sorted(paths):
        path = root / name
        if RUN.name in path.parts:
            continue
        with sqlite3.connect(f"{path.absolute().as_uri()}?mode=ro", uri=True) as db:
            cols = {x[1] for x in db.execute("PRAGMA table_info(samples)")}
            if "request_sha" not in cols:
                continue
            where = ",".join("?" for _ in keys)
            rows = db.execute(f"""SELECT unit_key, request_sha, status, request_json, response_json
                                  FROM samples WHERE request_sha IN ({where})""", tuple(keys)).fetchall()
        for unit, digest, status, request, response in rows:
            key = keys[digest]
            if not request or json.loads(request) != wires[key]:
                raise ValueError("Archived request digest cannot be verified")
            record = path.parent / "visible" / unit / "record.json"
            started = read(record).get("started_unix") if record.is_file() else None
            parsed = json.loads(response) if response else {}
            answer = parsed.get("answer")
            valid = status == "COMPLETE" and isinstance(answer, str) and bool(answer.strip())
            item = {"status": "OK" if valid else status, "answer": answer if valid else None,
                    "request_sha256": digest, "archive": name, "archive_unit": unit,
                    "started": started, "origin": "ARCHIVED_EXACT"}
            found.setdefault(key, []).append(item)
    chosen = {}
    for key, matches in found.items():
        matches.sort(key=lambda x: (x["status"] != "OK", x["started"] is None,
                                   x["started"] or 0, x["archive"], x["archive_unit"]))
        chosen[key] = {**matches[0], "archived_hits": len(matches)}
    return chosen, len(paths)


def merge_stage(stage, jobs, cache, identity, ledger):
    missing = {key: wire for key, wire in jobs.items() if key not in cache}
    fresh = engine.stage(stage, missing, identity, True, ledger) if missing else {}
    return {**cache, **fresh}


def historical_receipts(api, public, full, cached, cases):
    root = HERE.parents[2]
    runs = root / "runs" / HERE.parent.name
    builds = [HERE.parent / "native_residual_v1" / name for name in
              ("selected_gepa_expansion_v1", "persist_performance_v1")]
    builds.append(runs / "persist_selected_gepa_completion_v1")
    verified = {}
    branches = Counter()
    for folder in builds:
        stage_index = {
            stage: {x["unit"]["root_id"]: x["request"] for x in read(folder / f"{stage}_MANIFEST.json")["units"]
                    if x["unit"]["method"].removesuffix("/PersistJudge") == "SELECTED_GEPA"
                    and x["unit"]["root_id"] in cached}
            for stage in ("QueryRoute", "EvidenceSelect", "FinalActor", "PersistNative")
        }
        private = runs / folder.name
        for uid, old_actor in stage_index["FinalActor"].items():
            if uid in verified:
                raise ValueError("Duplicate archived selection")
            data = public[uid]
            route = receipt(private, "QueryRoute", uid, stage_index["QueryRoute"][uid])
            selector = receipt(private, "EvidenceSelect", uid, stage_index["EvidenceSelect"][uid])
            fork = api["transfer"].confirmation.route.decode(route, data["query"])
            branch = "style" if fork["check_history"] else "grounding"
            evidence = api["select"](cases[uid], data, route, selector)
            plan = read(root / "reports/qamc_persistbench_actor_factorial/PLAN.json")
            exact = api["actor_request"](cases[uid], data["query"], evidence, plan, plan["prompts"]["gepa"])
            prior = cached[uid]
            if branch != prior["branch"] or exact != old_actor or sha(exact) != prior["actor_sha256"]:
                raise ValueError("Routed Actor reconstruction differs from its actual request")
            answer = receipt(private, "FinalActor", uid, old_actor)
            if answer != prior["answer"]:
                raise ValueError("Routed answer changed")
            judge_wire = stage_index["PersistNative"][uid]
            score_raw = receipt(private, "PersistNative", uid, judge_wire)
            scorer = api["persist"].author.ext.parent.persist
            parsed = scorer.score(cases[uid]["category"], score_raw)
            if any(prior["score"][k] != v for k, v in parsed.items()):
                raise ValueError("Historical score does not match its receipt")
            verified[uid] = {"branch": branch, "selected_sha256": sha(evidence),
                             "selected_count": len(evidence), "judge_wire": judge_wire}
            branches[branch] += 1
    if verified.keys() != full.keys():
        raise ValueError("Missing exact selected evidence")
    return verified, branches


def prepare():
    count, api, public, full, baseline, cases, judge, bounds, _ = inventory()
    verified, branches = historical_receipts(api, public, full, baseline, cases)
    for uid, data in verified.items():
        if normalized(data["judge_wire"], baseline[uid]["answer"]) != bounds[uid]:
            raise ValueError("Historical grading envelope changed")
    actor_cache, scanned = archived({(uid, "FULL"): wire for uid, wire in full.items()}, HERE.parents[2])
    pin = {"archive_sha256": sha({uid: row for (uid, _), row in actor_cache.items()}), "roster": sorted(full), "cap": len(full) * len(STAGES),
           "actor_sha256": sha(full), "prior_answers_sha256": sha(baseline),
           "prior_verified_sha256": sha(verified),
           "criteria_sha256": sha((HERE / "EXTENSION_PROTOCOL.md").read_bytes()),
           "runner_sha256": sha(Path(__file__).read_bytes())}
    info = {"roots": len(full), "exact_archived_chains": len(verified), "branches": branches,
            "source_join_sha256": count["candidate_join_sha256"], "cap": pin["cap"]}
    info.update(local_ledgers_checked=scanned, cached_full_actors=len(actor_cache),
                cached_full_actor_statuses=Counter(row["status"] for row in actor_cache.values()),
                archived_actor_hits=sum(row["archived_hits"] for row in actor_cache.values()))
    return pin, info, api, public, full, baseline, cases, judge, bounds, actor_cache


def run(pin, info, api, public, full, baseline, cases, judge, bounds, actor_cache):
    if read(RUN / "FROZEN.json") != pin:
        raise ValueError("Frozen historical comparison drift")
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = dict.fromkeys(STAGES, len(full))
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    scorer = api["persist"].author.ext.parent.persist
    _, rubrics, fmt = scorer.upstream()
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)
        actors = merge_stage(STAGES[0], {(u, "FULL"): w for u, w in full.items()},
                             actor_cache, identity, ledger)
        jobs = {}
        for (uid, arm), result in actors.items():
            if result["status"] != "OK":
                continue
            case, task = cases[uid], public[uid]
            answer = result["answer"]
            wire = api["persist"].author.ext.text_request(
                rubrics[case["category"]], fmt["build_judge_prompt"](task["memories"], task["query"], answer),
                judge["model"], judge["stages"][api["persist"].STAGE]["max_tokens"])
            if normalized(wire, answer) != bounds[uid]:
                raise ValueError("Fresh native grade envelope differs from archived ROUTED")
            jobs[uid, arm] = wire
        judge_cache, _ = archived(jobs, HERE.parents[2])
        probe.freeze(RUN / "GRADE_CACHE.json", {uid: row for (uid, _), row in judge_cache.items()})
        replies = merge_stage(STAGES[1], jobs, judge_cache, identity, ledger)
        info["cached_full_grades"] = len(judge_cache)
        result = []
        for (uid, arm), actor in actors.items():
            judge_reply = replies.get((uid, arm), {})
            grade = None
            status = judge_reply.get("status", actor["status"])
            if judge_reply.get("status") == "OK":
                try:
                    grade = scorer.score(cases[uid]["category"], judge_reply["answer"])
                except (ValueError, TypeError, KeyError):
                    status = "INVALID_SCORE"
            result.append({"uid": uid, "status": status, "routed": baseline[uid], "actor": actor,
                           "judge": judge_reply, "full_score": grade})
        if len(ledger) > pin["cap"]:
            raise ValueError("Unexpected extension calls")
        probe.freeze(RUN / "RESULTS.json", {"rows": result, "ledger": ledger, "info": info})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("check", "freeze", "run"))
    query = cli.parse_args()
    pin, info, *inputs = prepare()
    if query.action == "freeze":
        probe.freeze(RUN / "FROZEN.json", pin)
    if query.action == "run":
        run(pin, info, *inputs)
    print(json.dumps(info, sort_keys=True))
