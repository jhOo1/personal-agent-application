"""Compare free commitment with mechanically compiled conditional actions."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
OLD = run_path(str(HERE.parent / "protected_clause_exposure_v1/trial.py"))
RUN = OLD["RUN"].with_name(HERE.name)
PRIVATE = RUN / "private"
archive, engine, probe, sha, read = (OLD[key] for key in ("archive","engine","probe","sha","read"))
ARMS = ("FREE","BRANCH")
PLANNER = """Read only the present task, context and fixed facts. Decide whether an unknown current-task condition would materially change one deliverable decision. Exclude incidental uncertainty that does not affect the main action. If the task already specifies that choice, or a usable answer does not depend on such uncertainty, output {"mode":"NONE"}. Otherwise produce two genuinely distinct and feasible actions for when a concrete, checkable criterion is met versus not met. The decision must serve the existing requested deliverable. Do not infer personal history, factual availability, or the missing condition itself. Both actions must respect all explicit task constraints. Return JSON only: {"mode":"BRANCH","query_quote":"exact current query words","decision":"what must be decided","criterion":"observable condition","if_met":"one complete action","if_not_met":"a different complete action"}. Use the task's language."""
SHARED = """Complete the original current task in the requested language and document format. Use historical information only when genuinely applicable to the task and affected people. Protect all fixed facts, applicable hard requirements, and legitimate preferences. Do not turn private opinion into a generally binding factual or team rule. The candidate actions were derived from the present task without memory; they are possible plans and may lack necessary details. Never invent or assume the value of an unknown condition. Do not quote any internal labels or expose historical details unnecessarily."""
NOTES = {
    "FREE":"Use the decision aid as optional planning information. Choose and deliver the best concrete answer, with conditional alternatives where you judge useful.",
    "BRANCH":"Execute the conditional decision map. If available task evidence establishes the criterion, render the corresponding action. If its value is still unknown, communicate both distinct actions and when to choose each. Ensure that both preserve legitimate constraints and together still form a directly usable answer. Do not turn one alternative into the universal default. You may refine each action to fit the actual requirements and deliverable.",
}


def compile_plan(raw, query):
    obj = OLD["parse_object"](raw)
    if obj == {"mode":"NONE"}:
        return None
    required = {"mode","query_quote","decision","criterion","if_met","if_not_met"}
    if not isinstance(obj,dict) or set(obj) != required or obj["mode"] != "BRANCH":
        raise ValueError("Invalid task plan contract")
    for key,val in obj.items():
        if not isinstance(val,str) or not 1 <= len(val.strip()) <= 450:
            raise ValueError(f"Invalid plan field: {key}")
    if obj["query_quote"] not in query:
        raise ValueError("Query quote does not occur")
    normalize = lambda value: "".join(value.lower().split())
    if normalize(obj["if_met"]) == normalize(obj["if_not_met"]):
        raise ValueError("Identical actions")
    if normalize(obj["criterion"]) in (normalize(obj["if_met"]),normalize(obj["if_not_met"])):
        raise ValueError("Condition and action are identical")
    return obj


def packets(card, plan):
    jobs = {}
    for arm in ARMS:
        wire = deepcopy(card["wire"])
        block = dict(decision=plan["decision"],criterion=plan["criterion"],
                     actions={"if_met":plan["if_met"],"if_not_met":plan["if_not_met"]})
        wire["messages"][0]["content"] += "\n\n" + SHARED + "\n" + json.dumps(block,ensure_ascii=False) + "\n" + NOTES[arm]
        OLD["validate_public_request"](wire)
        jobs[arm] = wire
    return jobs


def build():
    previous,cards,_ = OLD["build"]()
    if previous != read(OLD["PRIVATE"]/"FREEZE.json"):
        raise ValueError("Archived panel or exact incumbent differs")
    jobs = {}
    for uid,card in cards.items():
        task = {k:v for k,v in card["packet"].items()
                if k in {"query","current_context","facts","fixed_facts"}}
        wire = archive.body(PLANNER, task, 4096)
        OLD["validate_public_request"](wire)
        jobs[uid,"SHARED"] = wire
    pin = dict(previous=sha(previous),wires=[[uid,sha(w)] for (uid,_),w in jobs.items()],
               code=sha(Path(__file__).read_bytes()),protocol=sha((HERE/"PROTOCOL.md").read_bytes()),
               service=probe.read_reference()[1])
    return pin,cards,jobs


def run(pin,cards,jobs):
    probe.RUN,probe.OUT,engine.OUT = RUN,PRIVATE,PRIVATE
    engine.CAP = {"BranchPlan":12,"BranchActor":24,engine.RPE:8,"BenchAttrs":26,"PersistNative":12}
    identity = {"experiment_sha256":sha(pin),"service_reference_sha256":pin["service"]}
    ledger,audits,rows = [],{},[]
    with probe.runner_lock(RUN/"runner.lock"):
        def stage(name,pending,cache=None):
            return engine.stage(name,pending,identity,True,ledger,cache) if pending else {}
        choices = stage("BranchPlan",jobs)
        final_jobs = {}
        for (uid,_), reply in choices.items():
            status,plan = reply["status"],None
            if status == "OK":
                try:
                    plan = compile_plan(reply["answer"],cards[uid]["packet"]["query"])
                except (ValueError,TypeError):
                    status = "INVALID_PLAN"
            audits[uid] = dict(status=status,plan=plan)
            if plan:
                final_jobs.update({(uid,arm):w for arm,w in packets(cards[uid],plan).items()})
        replies = stage("BranchActor",final_jobs)
        for uid,item in cards.items():
            card,audit = item["card"],audits[uid]
            for arm in ARMS:
                row = {k:card[k] for k in ("benchmark","group","stratum")}
                row.update(uid=uid,method=arm,answer=None,score=None,score_flags=None,
                           sources=item["packet"]["source_evidence"],actor_status=audit["status"],
                           disposition="PLAN_MISSING")
                if audit["status"] == "OK" and audit["plan"] is None:
                    row.update(answer=card["base_answer"],score=card["base_score"],
                               score_flags=card["base_flags"],disposition="EXACT_BASE")
                elif (uid,arm) in replies:
                    reply = replies[uid,arm]
                    row.update(answer=reply.get("answer"),actor_status=reply["status"],disposition="TRIGGERED")
                if row["answer"]:
                    row["answer_sha256"] = sha(row["answer"])
                rows.append(row)
        OLD["grading"](rows,stage)
        probe.freeze(PRIVATE/"SETTLED.json",dict(rows=rows,audits=audits,ledger=ledger))


def report(cards):
    record = read(PRIVATE/"SETTLED.json")
    ledger = record["ledger"]
    def key(r):
        return r["unit"]["stage"],r["request_sha256"],r["status"]
    actual = [read(p) for p in RUN.glob("*/visible/*/record.json")]
    if Counter(map(key,actual)) != Counter(map(key,ledger)):
        raise ValueError("Physical accounting mismatch")
    eligibility = {}
    for uid,audit in record["audits"].items():
        group = cards[uid]["card"]["benchmark"]
        counts = eligibility.setdefault(group,Counter())
        counts["unknown" if audit["status"] != "OK" else "triggered" if audit["plan"] else "unchanged"] += 1
    rows = []
    for r in record["rows"]:
        detail = dict(case=r["uid"].split("/",1)[-1],benchmark=r["benchmark"],stratum=r["stratum"],
                      arm=r["method"],status=r["actor_status"],disposition=r["disposition"],
                      score=OLD["metric"](r),score_flags=r.get("score_flags"),
                      bias={k:r["score"].get(k) for k in ("OPB","UPB","FM")}
                           if r["benchmark"]=="RPEval" and r["score"] else None)
        rows.append(detail)
    print(json.dumps(dict(eligibility=eligibility,rows=rows,physical=Counter(r["status"] for r in ledger),
                         stages=Counter(r["unit"]["stage"] for r in ledger),
                         tokens=sum((r["usage"] or {}).get("total_tokens",0) for r in ledger),
                         unknown_usage=sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                         retries=sum(r["automatic_retries"] for r in ledger)),indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("freeze","run","report"))
    action=parser.parse_args().action
    pin,cards,jobs=build()
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=PRIVATE/"FREEZE.json"
    if action=="freeze":
        probe.freeze(path,pin)
        print(Counter(c["card"]["benchmark"] for c in cards.values()))
    elif read(path)!=pin:
        raise ValueError("Frozen task condition protocol changed")
    elif action=="run":
        run(pin,cards,jobs)
    else:
        report(cards)
