"""Replay frozen IPE-C and RP endpoints on one common second backbone."""
import argparse
from collections import Counter
import json
from pathlib import Path

import replay_panel as archive
from qamc.common import parse_object, sha
from qamc_rpeval_terminal_judge_sensitivity import inspect
from proposals.qamc_rpreasoner_paper.engine import rankings
from qamc_rpeval_formal_multi_run import assets, initial_bodies, legacy, task_for

HERE = Path(__file__).resolve().parent
v41, probe, engine = archive.v41, archive.probe, archive.engine
ESTIMATE, ACTOR = "BackboneEstimate", "BackboneActor"
FULL, ZERO, ROUTED = "RP_FULL", "TASK_ONLY", "IPE_C"
MODEL = "gpt-4.1"
STRATA = ("B_only", "contains_C", "all_A")
METRICS = ("OPB", "UPB", "FM")


def read(path):
    return json.loads(path.read_text())


def panel(rows, cases):
    selected, used = [], set()
    for stratum in STRATA:
        for track in ("explicit/multi", "implicit/multi"):
            candidates = sorted(
                [r for r in rows if r["stratum"] == stratum and cases[r["uid"]]["track"] == track],
                key=lambda row: sha(["cross-backbone-panel-v1", row["source_group"], row["uid"]]))
            n = 0
            for row in candidates:
                if row["source_group"] in used:
                    continue
                used.add(row["source_group"])
                selected.append(row)
                n += 1
                if n == 4:
                    break
            if n != 4:
                raise ValueError(f"Insufficient exposed groups for {stratum}/{track}")
    return sorted(selected, key=lambda row: sha(["cross-backbone-execution", row["uid"]]))


def compose_plan():
    saved = read(v41.OUT / "FROZEN.json")
    if saved["independent_confirmation"]:
        raise ValueError("Archive must be exposed")
    roots = {x["uid"]:x for x in saved["roots"]}
    parent = read(v41.formal.OUT / "PLAN.json")
    cases = v41.author_cases(parent)
    frontier = read(archive.BASE / "selective_path_frontier_v1/RESULTS.json")
    labels = {r["uid"]: r["labels"] for r in read(archive.ZERO_OUT / "RESULTS.json")["roots"]}
    cards = []
    for row in panel(frontier["rows"],cases):
        uid = row["uid"]
        task = task_for(cases[uid])
        rank = dict(initial_bodies(task, v41.RP))
        zero = v41.task_only_request(roots[uid])
        requests = {role:{**rank[role], "model":MODEL} for role in ("RPR_MLE","RPR_IPE")}
        cards.append({"uid":uid, "source_group":row["source_group"], "track":cases[uid]["track"],
                      "stratum":row["stratum"], "estimators":requests, "task_only":{**zero,"model":MODEL},
                      "qwen_path": row["base"], "qwen_reference": {m:row["cells"][m] for m in (v41.RP,ZERO)}})
    plan = {"cards":cards,"model_alias":MODEL,"native_grade_alias":"gpt-4.1","score_scope":"adaptation",
            "maximum_requests":{"estimator": len(cards)*2,"actor":len(cards)*2,"judge":len(cards)*2},
            "code_sha256":sha(Path(__file__).read_bytes()), "old_panel_sha256":sha(saved)}
    return plan, roots, parent, cases, labels


def estimate(answer, task):
    value = parse_object(answer)
    for row in value.get("rankings", []):
        order = row.get("order")
        if isinstance(order, list) and len(order) == 3 and all(isinstance(c,str) and len(c)==1 for c in order):
            row["order"] = "".join(order)
    return value, rankings(task, value)


def compile_full(case, estimates, paper, root):
    public = task_for(case)
    value = {}
    for name in ("RPR_MLE","RPR_IPE"):
        if estimates[name]["status"] != "OK":
            return None, None, estimates[name]["status"]
        try:
            value[name] = estimate(estimates[name]["answer"], public)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            return None, None, f"INVALID_ESTIMATE: {exc}"
    m, p = value["RPR_MLE"][0], value["RPR_IPE"][0]
    wire = legacy.rpr.generator_request(public, paper, m, p)["request"]
    message = json.loads(wire["messages"][1]["content"])
    if message["source_evidence"] != root["original_sources"] or any(message[k]!=v for k,v in root["public_task"].items()):
        raise ValueError("Second backbone changed task or candidate evidence")
    route = FULL if any(s[0]=="C" for s in value["RPR_IPE"][1].values()) else ZERO
    return {**wire,"model":MODEL},route,None


def score_of(uid, method, reply, actor, labels):
    if not reply or reply["status"]!="OK":
        return {"grade":{},"flags":None, "issue": reply["status"] if reply else "UNSCORED"}
    try:
        grade, errors = probe.fields(parse_object(reply["answer"]), len(labels), True)
    except (KeyError,TypeError,ValueError) as exc:
        return {"grade":{},"flags":None,"issue":str(exc)}
    record = {"uid":uid,"method":method,"answer":actor["answer"],"native_fields":grade,
              "raw_scores":{v41.NATIVE:reply["answer"]}}
    observed = inspect(record,labels) if "match" in grade else None
    return {"grade":grade,"flags":observed["flags"] if observed else None,"issue":errors}


def summarize(rows):
    out = {}
    for scope in ("all",*STRATA):
        chosen = [r for r in rows if scope=="all" or r["stratum"]==scope]
        out[scope] = {"assigned": len(chosen)}
        common = [r for r in chosen if all(r["scores"][m]["grade"].get("match") for m in (ROUTED,FULL,ZERO))]
        for name, subset in (("strict",common),("flag_excluded",[r for r in common if all(
                r["scores"][m]["flags"]==[] for m in (ROUTED,FULL,ZERO))])):
            table = {"uids":len(subset),"positions":sum(len(r["labels"]) for r in subset),
                     "routed_full":sum(r["branch"]==FULL for r in subset),"methods":{}}
            for method in (ROUTED,FULL,ZERO):
                cells = [r["scores"][method]["grade"] for r in subset]
                table["methods"][method] = {"match":sum(c["match"]["matched"] for c in cells),
                    "whole":sum(c["match"]["matched"]==c["match"]["positions"] for c in cells),
                    **{k:{"total":sum(c[k] for c in cells if k in c),"uids":sum(k in c for c in cells)} for k in METRICS}}
            qwen = {m:0 for m in (ROUTED,FULL,ZERO)}
            for row in subset:
                old = row["qwen_reference"]
                for m,key in ((ROUTED,row["qwen_path"]),(FULL,v41.RP),(ZERO,ZERO)):
                    qwen[m]+=old[key]["matched"]
            table["qwen_same_uid_match"] = qwen
            out[scope][name] = table
    return out


def execute(action,data):
    plan, roots, parent, cases, labels = data
    probe.OUT = engine.OUT = HERE
    probe.RUN = engine.RUN.with_name(HERE.name)
    engine.CAP = {ESTIMATE:plan["maximum_requests"]["estimator"],
                  ACTOR:plan["maximum_requests"]["actor"],engine.RPE:plan["maximum_requests"]["judge"]}
    identity = {"experiment_sha256":sha(plan),"service_reference_sha256":probe.read_reference()[1]}
    ledger, live = [], action=="run"

    def stage(name,jobs):
        return engine.stage(name,jobs,identity,live,ledger) if jobs else {}

    with probe.runner_lock(probe.RUN/"runner.lock"):
        probe.freeze(HERE/"EXECUTION.json",identity)
        estimates = stage(ESTIMATE,{(r["uid"],k):v for r in plan["cards"] for k,v in r["estimators"].items()})
        jobs, summaries = {}, []
        paper = assets()[3]
        for card in plan["cards"]:
            uid = card["uid"]
            submitted = {k:estimates[uid,k] for k in card["estimators"]}
            full, branch, error = compile_full(cases[uid],submitted,paper,roots[uid])
            jobs[uid,ZERO] = card["task_only"]
            if full:
                jobs[uid,FULL] = full
            summaries.append({k:card[k] for k in ("uid","track","source_group","stratum","qwen_path","qwen_reference")})
            summaries[-1].update(branch=branch,estimate_error=error,estimator_results=submitted)
        actors = stage(ACTOR,jobs)
        wires = {(uid,arm):engine.rpe_wire(parent,cases[uid],{"uid":uid,"actor_status":"OK","answer":entry["answer"]})
                 for (uid,arm),entry in actors.items() if entry["status"]=="OK"}
        grades = stage(engine.RPE,wires)
        for row in summaries:
            uid = row["uid"]
            row["labels"] = labels[uid]
            row["actor"] = {arm:actors.get((uid,arm)) for arm in (FULL,ZERO)}
            row["judge"] = {arm:grades.get((uid,arm)) for arm in (FULL,ZERO)}
            scores = {arm:score_of(uid,arm,row["judge"][arm],row["actor"][arm],row["labels"]) for arm in (FULL,ZERO)}
            scores[ROUTED] = scores.get(row["branch"],{"grade":{},"flags":None,"issue":row["estimate_error"]})
            row["scores"] = scores
        result = {"summary":summarize(summaries),"rows":summaries,"ledger":ledger,
                  "calls":Counter(r["unit"]["stage"] for r in ledger),
                  "statuses":Counter(r["status"] for r in ledger),
                  "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "unknown_usage":sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        path = HERE/"RESULTS.json"
        if live:
            probe.freeze(path,result)
        elif read(path)!=result:
            raise ValueError("Second-backbone result differs on replay")
        print({k:v for k,v in result.items() if k not in ("rows","ledger")})


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action",choices=("freeze","check","run","replay"))
    args = parser.parse_args()
    data = compose_plan()
    path = HERE/"FROZEN.json"
    if args.action=="freeze":
        probe.freeze(path,data[0])
    elif data[0]!=read(path):
        raise ValueError("Frozen cross-backbone plan drifted")
    elif args.action!="check":
        execute(args.action,data)
    print({"cards":len(data[0]["cards"]),"budget":data[0]["maximum_requests"]})
