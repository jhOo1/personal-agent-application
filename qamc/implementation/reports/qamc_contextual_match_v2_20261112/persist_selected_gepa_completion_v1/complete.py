"""Complete seven unissued, exposed rows of the exact SELECTED_GEPA pipeline."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "native_residual_v1"))


from persist_grounding_gepa_wires import actor_request, input_requests, select, transfer
from qamc.common import sha
from transfer_replay import persist
from trial_reassembly import engine, probe

archive = run_path(str(BASE / "persist_archived_headroom_v1/audit.py"))
AUTHOR, ROOT = archive["AUTHOR"], archive["ROOT"]
normalized, audit, read = (archive[k] for k in ("normalized", "audit", "read"))
get_author, passes = archive["get_author"], archive["passes"]
RUN = engine.RUN.with_name(HERE.name)
METHOD = "SELECTED_GEPA"
STAGES = ("QueryRoute", "EvidenceSelect", "FinalActor", "PersistNative")
AUDIT = ROOT / "runs" / BASE.name / "persist_archived_headroom_v1" / "AUDIT.json"


def prepare():
    evidence = audit()
    if evidence != read(AUDIT):
        raise ValueError("Archived outcome evidence drift")
    targets = [x for x in evidence["selected_gepa_uncovered"] if not x["actor_in_examined_manifests"]]
    if len(targets) != 7 or not all(x["base_pass"] for x in targets):
        raise ValueError("Unexpected unfinished protection roster")
    uids = {x["uid"] for x in targets}
    for dirname in ("selected_gepa_expansion_v1", "persist_performance_v1"):
        prior = BASE / "native_residual_v1" / dirname
        for stage in STAGES:
            manifest = read(prior / f"{stage}_MANIFEST.json")
            if any(x["unit"]["root_id"] in uids for x in manifest["units"]):
                raise ValueError("Earlier allocation found for planned row")
    for dirname in ("qamc_persistbench_actor_factorial", "qamc_persistbench_grounding_transfer"):
        if uids & read(ROOT / "reports" / dirname / "PLAN.json")["jobs"].keys():
            raise ValueError("Earlier selected method roster overlaps")

    author_plan = read(AUTHOR.parent / "PLAN.json")
    cases = {x["uid"]: x for x in author_plan["cases"] if x["uid"] in uids and x["role"] == "DEV"}
    if uids != cases.keys() or author_plan["not_confirmation"] is not True:
        raise ValueError("Exposed author manifest mismatch")
    archived, bounds, _ = get_author()
    old = {r["uid"]: r for r in archived if r["uid"] in uids and r["method"] == "PB_RUBRIC"}
    transfer_plan = read(transfer.OUT / "PLAN.json")
    protocol = read(ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    inputs, jobs = {}, {}
    for uid, case in cases.items():
        task = persist.author.parent.smoke.task_for(case)
        public = {"query": task.query, "memories": [m.text for m in task.memories]}
        if sha(public) != case["public_sha256"] or sha(old[uid]["actor_request"]) != old[uid]["actor_request_sha256"]:
            raise ValueError("Public or baseline generation drift")
        inputs[uid], jobs[uid] = public, input_requests(case, public, transfer_plan)
    pin = {"tasks": sorted(uids), "inputs": {u: {k: sha(w) for k, w in j.items()} for u, j in jobs.items()},
           "scorer_envelopes": {u: sha(bounds[u]) for u in uids},
           "actor_protocol": sha([protocol["protocols"], protocol["prompts"]["gepa"]]),
           "archive_evidence": sha(evidence), "launcher": sha(Path(__file__).read_bytes()),
           "protocol": sha((HERE / "PROTOCOL.md").read_bytes()), "cap": 28}
    return pin, cases, old, bounds, author_plan, protocol, inputs, jobs


def run(pin, cases, old, bounds, author_plan, protocol, inputs, jobs):
    if pin != read(RUN / "FROZEN.json"):
        raise ValueError("Runtime request freeze changed")
    engine.OUT = probe.OUT = probe.RUN = RUN
    engine.CAP = dict.fromkeys(STAGES, len(cases))
    ident = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    ledger = []
    scorer = persist.author.ext.parent.persist
    _, rubrics, fmt = scorer.upstream()
    judge_proto = author_plan["protocols"]["gpt41"]
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", ident)

        def dispatch(stage, wires, cache=None):
            return engine.stage(stage, {(u, METHOD): w for u, w in wires.items()},
                                ident, True, ledger, cache) if wires else {}

        routes = dispatch(STAGES[0], {uid: item["query"] for uid, item in jobs.items()})
        selectors, branches, failure = {}, {}, {}
        for (uid, _), row in routes.items():
            if row["status"] != "OK":
                failure[uid] = row["status"]
                continue
            try:
                route = transfer.confirmation.route.decode(row["answer"], inputs[uid]["query"])
                branches[uid] = "style" if route["check_history"] else "grounding"
                selectors[uid] = jobs[uid][branches[uid]]
            except (ValueError, KeyError, TypeError):
                failure[uid] = "INVALID_ROUTE"
        evidence_counts, actors = {}, {}
        for (uid, _), row in dispatch(STAGES[1], selectors).items():
            if row["status"] != "OK":
                failure[uid] = row["status"]
                continue
            try:
                evidence = select(cases[uid], inputs[uid], routes[uid, METHOD]["answer"], row["answer"])
                evidence_counts[uid] = len(evidence)
                actors[uid] = actor_request(cases[uid], inputs[uid]["query"], evidence, protocol,
                                            protocol["prompts"]["gepa"])
            except (ValueError, KeyError, TypeError):
                failure[uid] = "INVALID_SELECTION"
        answers = dispatch(STAGES[2], actors)
        grades, cached = {}, {}
        for (uid, _), row in answers.items():
            if row["status"] != "OK":
                failure[uid] = row["status"]
                continue
            category = cases[uid]["category"]
            public = inputs[uid]
            wire = persist.author.ext.text_request(
                rubrics[category], fmt["build_judge_prompt"](public["memories"], public["query"], row["answer"]),
                judge_proto["model"], judge_proto["stages"][persist.STAGE]["max_tokens"])
            if normalized(wire, row["answer"]) != bounds[uid]:
                raise ValueError("Judge changed more than the answer")
            grades[uid] = wire
            if row["answer"] == old[uid]["answer"]:
                cached[sha(wire)] = old[uid]["raw_scores"][persist.STAGE]
        judged = dispatch(STAGES[3], grades, cached)
        rows = []
        for uid, case in cases.items():
            category = case["category"]
            actor = answers.get((uid, METHOD), {})
            score, error = None, failure.get(uid)
            response = judged.get((uid, METHOD), {})
            if response.get("status") == "OK":
                try:
                    score = scorer.score(category, response["answer"])
                except (ValueError, KeyError, TypeError):
                    error = "INVALID_SCORE"
            elif response:
                error = response["status"]
            rows.append({"uid": uid, "method": METHOD, "category": category,
                         "actor_status": actor.get("status", "UNISSUED"), "error": error,
                         "answer": actor.get("answer"), "score": score, "judge": response,
                         "original_score": old[uid]["score"], "branch": branches.get(uid),
                         "visible_memories": evidence_counts.get(uid)})
        probe.freeze(RUN / "RESULTS.json", {"rows": rows, "ledger": ledger})


def summarize():
    result = read(RUN / "RESULTS.json")
    evidence = read(AUDIT)
    combined = {k.split("/")[0]: Counter(v) for k, v in evidence["comparisons"].items()
                if k.endswith("/SELECTED_GEPA")}
    rows = []
    missing = 0
    for r in result["rows"]:
        track = r["category"]
        valid = r["score"] is not None
        if valid:
            passed = passes(r["score"], track)
            assert passes(r["original_score"], track)
            for name in ("all", track):
                combined[name].update(common=1, base_pass=1, other_pass=passed, losses=not passed)
        else:
            missing += 1
        rows.append({k: r[k] for k in ("uid", "category", "branch", "visible_memories", "score", "error")})
    ledger = result["ledger"]
    return {"combined": combined, "rows": rows, "missing_in_50": 1 + missing,
            "requests": len(ledger), "statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "check", "run", "summary"))
    action = parser.parse_args().action
    if action == "summary":
        print(json.dumps(summarize(), indent=2, sort_keys=True))
    else:
        args = prepare()
        if action == "freeze":
            probe.freeze(RUN / "FROZEN.json", args[0])
        elif action == "check":
            if args[0] != read(RUN / "FROZEN.json"):
                raise ValueError("Stale frozen plan")
        else:
            run(*args)
        print(json.dumps({"tasks": len(args[1]), "freeze_sha256": sha(args[0])}))
