"""Recover only never-dispatched history answers after whitespace-only rank errors."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

import cross_backbone as v
from qamc.common import parse_object, sha

HERE = v.HERE/"format_recovery"


def decode(receipt):
    data = parse_object(receipt["answer"])
    edited = 0
    for row in data.get("rankings", []):
        text = row.get("order")
        if not isinstance(text,str) or re.fullmatch(r"[ABC\s]+",text) is None:
            continue
        # Preserve every label and its position. The unchanged strict validator
        # checks candidate coverage and semantic validity after normalization.
        order = "".join(text.split())
        if len(order)==3 and set(order)==set("ABC") and text!=order:
            row["order"] = order
            edited += 1
    return {**receipt,"answer":json.dumps(data,ensure_ascii=False)} if edited else receipt


def prepare():
    plan, roots, parent, cases, labels = v.compose_plan()
    if plan != v.read(v.HERE/"FROZEN.json"):
        raise ValueError("Original experiment's run code or inputs drifted")
    original = v.read(v.HERE/"RESULTS.json")
    prior_rows = {r["uid"]:r for r in original["rows"]}
    manifest_path = v.HERE/f"{v.ACTOR}_MANIFEST.json"
    old_history_requests = {u["unit"]["root_id"] for u in v.read(manifest_path)["units"]
                            if u["unit"]["method"]==v.FULL}
    approved, changes = {}, {}
    for card in plan["cards"]:
        uid = card["uid"]
        row = prior_rows[uid]
        if not row["estimate_error"] or row["actor"][v.FULL] or uid in old_history_requests:
            continue
        editors = {role:decode(receipt) for role,receipt in row["estimator_results"].items()
                   if receipt["status"]=="OK"}
        if editors.keys()!=row["estimator_results"].keys() or editors==row["estimator_results"]:
            continue
        wire,branch,error = v.compile_full(cases[uid],editors,v.assets()[3],roots[uid])
        if not wire or not branch or error:
            continue
        approved[uid] = {"actor":wire,"branch":branch,
                         "old_failed_contract":row["estimate_error"]}
        changes[uid] = {role:{"response_sha256":sha(row["estimator_results"][role]["answer"]),
                              "normalized_sha256":sha(receipt["answer"])}
                        for role,receipt in editors.items() if receipt!=row["estimator_results"][role]}
    config = {"source_results_sha256":sha(original),"original_actor_manifest_sha256":sha(v.read(manifest_path)),
              "code_sha256":sha(Path(__file__).read_bytes()),"eligible":approved,"normalized":changes,
              "new_judge_cap":len(approved),"new_estimator_cap":0}
    return config,original,parent,cases,labels


def execute(action,data):
    config, original, parent, cases, labels = data
    v.probe.OUT = v.engine.OUT = HERE
    v.probe.RUN = v.engine.RUN.with_name(f"{v.HERE.name}_format_recovery")
    count = len(config["eligible"])
    v.engine.CAP = {v.ACTOR:count,v.engine.RPE:count}
    identity = {"experiment_sha256":sha(config),"service_reference_sha256":v.probe.read_reference()[1]}
    ledger, live = [], action=="run"

    def stage(name,jobs):
        return v.engine.stage(name,jobs,identity,live,ledger) if jobs else {}

    with v.probe.runner_lock(v.probe.RUN/"runner.lock"):
        v.probe.freeze(HERE/"EXECUTION.json",identity)
        actors = stage(v.ACTOR,{(uid,v.FULL):r["actor"] for uid,r in config["eligible"].items()})
        jobs = {(uid,arm):v.engine.rpe_wire(parent,cases[uid],
                    {"uid":uid,"actor_status":"OK","answer":r["answer"]})
                for (uid,arm),r in actors.items() if r["status"]=="OK"}
        grades = stage(v.engine.RPE,jobs)
        rows = deepcopy(original["rows"])
        for row in rows:
            uid = row["uid"]
            if uid not in config["eligible"]:
                continue
            actor, grade = actors[uid,v.FULL], grades.get((uid,v.FULL))
            row["branch"] = config["eligible"][uid]["branch"]
            row["actor"][v.FULL], row["judge"][v.FULL] = actor, grade
            row["scores"][v.FULL] = v.score_of(uid,v.FULL,grade,actor,labels[uid])
            row["scores"][v.ROUTED] = row["scores"][row["branch"]]
        result = {"summary":v.summarize(rows),"rows":rows,"ledger":ledger,
                  "calls":Counter(r["unit"]["stage"] for r in ledger),
                  "statuses":Counter(r["status"] for r in ledger),
                  "tokens":sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "unknown_usage":sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        output = HERE/"RESULTS.json"
        if live:
            v.probe.freeze(output,result)
        elif v.read(output)!=result:
            raise ValueError("Normalized ranking replay drift")
        print({k:v for k,v in result.items() if k not in ("rows","ledger")})


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action",choices=("freeze","check","run","replay"))
    args = parser.parse_args()
    prepared = prepare()
    config = prepared[0]
    path = HERE/"FROZEN.json"
    if args.action=="freeze":
        v.probe.freeze(path,config)
    elif v.read(path)!=config:
        raise SystemExit("Formatting recovery freeze drift")
    elif args.action!="check":
        execute(args.action,prepared)
    print({"eligible":len(config["eligible"]),"new_judge_cap":config["new_judge_cap"]})
