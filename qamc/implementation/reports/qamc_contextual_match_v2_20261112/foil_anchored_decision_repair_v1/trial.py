"""A source-exact contrast gate for atomic final-decision edits."""
import argparse
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = run_path(str(BASE/"protected_clause_exposure_v1/trial.py"))
DREW = run_path(str(BASE/"archive_edit_opportunity_v1/run_drew.py"))
archive,engine,probe,sha,read = (OLD[k] for k in ("archive","engine","probe","sha","read"))
RUN = OLD["RUN"].with_name(HERE.name)
PRIVATE = RUN/"private"
ARMS = ("ORDINARY","FOIL")
QUOTAS = {"RPEval":4,"BenchPreS":2,"PersistBench":6}
TARGETS = ("implicit/094","explicit/116","0613beea","a47fceb8","b664c8fa","8bf01e01","a3e8272d")
SEED = "foil-anchored-decision-repair-v1"
COMMON = DREW["COMMON"] + """
The archived task-only foil is an alternative approach, not a correct answer or extra evidence.
Consult the actual Query, task facts and original history. Retain currently applicable preferences
and facts even when the foil overlooks them. Correct unsupported or misplaced decisions
without copying a whole foil. The final edited draft must directly fulfill the requested deliverable.
"""
FOIL = """
Before editing, locate a concrete primary action, choice or requirement in the strong draft that
differs from the foil and is unnecessary or wrong for the current task. The alternate shows the
decision can be made differently; it does not establish that memory caused the difference.
If no such harmful difference is supported, keep the draft. Otherwise include a witness object:
{"edits":[...],"witness":{"draft_quote":"a unique verbatim action in the strong draft being changed",
"foil_quote":"a unique verbatim action showing the contrasting decision in the foil",
"query_quote":"exact current Query words licensing the correction"}}.
Change all dependent recommendations that enforce that bad choice. Keep concrete applicable task
constraints and good personalized choices. Do not create assumptions to reach a preferred alternative.
"""


def foils():
    maps = {domain:{} for domain in QUOTAS}
    rpe_rows = read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    for item in rpe_rows:
        state = item["no_history_state"]
        if item["old_route"] == "REUSE_RP" and state.get("status") == "OK" and state.get("answer"):
            digest = item["controls"]["TASK_ONLY"]["answer_sha256"]
            if sha(state["answer"]) != digest:
                raise ValueError("Archived no-history answer hash differs")
            maps["RPEval"][item["uid"]] = (state["answer"], item["task_wire_sha256"] or digest)
    pb_rows = read(RUN.parent/"persist_exposure_fr3_v1/RESULTS.json")["rows"]
    for item in pb_rows:
        if item["repeat"] != 1:
            continue
        cell = item["methods"]["EMPTY"].get("actor")
        if cell and cell["status"] == "OK" and cell.get("answer"):
            maps["PersistBench"][item["uid"]] = (cell["answer"],cell["request_sha256"])
    feedback = read(BASE/"execution_feedback_policy_v1/RESULTS.json")["rows"]
    for item in feedback:
        if item["benchmark"]=="BenchPreS" and item["method"]=="EMPTY" and item["actor_status"]=="OK":
            if item.get("visible_ids"):
                raise ValueError("Bench empty foil had historical evidence")
            maps["BenchPreS"][item["uid"]] = (item["answer"],item["actor_request_sha256"])
    return maps


def build():
    sources = read(BASE/"transactional_reassembly_v1/FROZEN.json")
    if not sources["exposed_development_only"]:
        raise ValueError("Expected exposed archives")
    pool = foils()
    cards,jobs = {},{}
    for domain,limit in QUOTAS.items():
        used = set()
        eligible = []
        for source in sources["rows"]:
            uid = source["uid"]
            if source["benchmark"] != domain or uid not in pool[domain]:
                continue
            foil,ref = pool[domain][uid]
            if not isinstance(foil,str) or not foil.strip() or not ref or foil == source["base_answer"]:
                continue
            if sha(source["base_answer"].strip()) != source["baseline_answer_sha256"]:
                raise ValueError("Strong archive digest mismatch")
            if source["base_answer"] != source["base_answer"].strip():
                continue
            if not source["packet"]["source_evidence"]:
                continue
            rank = next((i for i,x in enumerate(TARGETS) if x in uid),100)
            eligible.append((rank,sha([SEED,source["group"],uid]),uid,source,foil,ref))
        for _,_,uid,source,foil,ref in sorted(eligible):
            if source["group"] in used:
                continue
            packet = {k:v for k,v in source["packet"].items() if k != "draft_units"}
            packet.update(draft=source["base_answer"],task_only_foil=foil)
            for arm in ARMS:
                wire = archive.body(COMMON + (FOIL if arm=="FOIL" else ""),packet,8192)
                OLD["validate_public_request"](wire)
                jobs[uid,arm] = wire
            if jobs[uid,"FOIL"]["messages"][1] != jobs[uid,"ORDINARY"]["messages"][1]:
                raise ValueError("Matched payload differs")
            cards[uid] = dict(source=source,foil=foil,reference=ref)
            used.add(source["group"])
            if len(used) == limit:
                break
        if len(used)!=limit:
            raise ValueError(f"Insufficient verified foils for {domain}: {len(used)}, {len(eligible)} eligible")
    frozen = dict(original=sha(sources),
                  foil={uid:sha([c["reference"],c["foil"]]) for uid,c in cards.items()},
                  wires=[[uid,arm,sha(w)] for (uid,arm),w in jobs.items()],
                  code=sha(Path(__file__).read_bytes()),protocol=sha((HERE/"PROTOCOL.md").read_bytes()),
                  service=probe.read_reference()[1])
    return frozen,cards,jobs


def apply(raw,card,arm):
    obj = OLD["parse_object"](raw)
    source = card["source"]
    if not isinstance(obj,dict) or not isinstance(obj.get("edits"),list):
        raise ValueError("Invalid edit envelope")
    if not obj["edits"]:
        if set(obj)!={"edits"}:
            raise ValueError("Unexpected fields for KEEP")
        return source["base_answer"]
    if arm == "FOIL":
        if set(obj)!={"edits","witness"}:
            raise ValueError("Exact contrasted decision witness required")
        witness = obj["witness"]
        if not isinstance(witness,dict) or set(witness)!={"draft_quote","foil_quote","query_quote"} or any(
                not isinstance(v,str) or len(v.strip())<5 for v in witness.values()):
            raise ValueError("Malformed contrasting actions")
        base,foil = source["base_answer"],card["foil"]
        draft_q,foil_q = witness["draft_quote"],witness["foil_quote"]
        if base.count(draft_q)!=1 or foil.count(foil_q)!=1 or draft_q.strip()==foil_q.strip():
            raise ValueError("Unverified or identical contrasting quote")
        if witness["query_quote"] not in source["packet"]["task"]["query"]:
            raise ValueError("Current task anchor does not match")
        left,right = base.index(draft_q),base.index(draft_q)+len(draft_q)
        anchors = [e.get("old") for e in obj["edits"] if isinstance(e,dict)]
        if not any(isinstance(s,str) and s and base.count(s)==1
                   and base.index(s)<right and base.index(s)+len(s)>left for s in anchors):
            raise ValueError("No replacement touches the witnessed action")
    elif set(obj)!={"edits"}:
        raise ValueError("Unexpected ordinary edit fields")
    return DREW["apply"](json.dumps({"edits":obj["edits"]},ensure_ascii=False),source,"ORDINARY")


def run(pin,cards,jobs):
    probe.RUN,probe.OUT,engine.OUT = RUN,PRIVATE,PRIVATE
    engine.CAP = {"FoilRevision":24,engine.RPE:8,"BenchAttrs":26,"PersistNative":12}
    identity = {"experiment_sha256":sha(pin),"service_reference_sha256":pin["service"]}
    ledger,rows = [],[]
    with probe.runner_lock(RUN/"runner.lock"):
        def stage(name,requests,cache=None):
            return engine.stage(name,requests,identity,True,ledger,cache) if requests else {}
        replies=stage("FoilRevision",jobs)
        for (uid,arm),receipt in replies.items():
            card=cards[uid]
            source=card["source"]
            row={k:source[k] for k in ("uid","benchmark","group","stratum")}
            row.update(method=arm,status=receipt["status"],actor_status=receipt["status"],
                       answer=None,score=None,score_flags=None,disposition="DELIVERY_MISSING",
                       sources=source["packet"]["source_evidence"])
            if receipt["status"]=="OK":
                try:
                    row["answer"]=apply(receipt["answer"],card,arm)
                    row["disposition"]="TRIGGERED" if row["answer"]!=source["base_answer"] else "EXACT_BASE"
                except (ValueError,KeyError,TypeError,AttributeError):
                    row.update(answer=source["base_answer"],disposition="CONTRACT_FALLBACK")
                row["answer_sha256"]=sha(row["answer"])
                if row["answer_sha256"]==source["baseline_answer_sha256"]:
                    row.update(score=source["base_score"],score_flags=source["base_flags"])
            rows.append(row)
        OLD["grading"](rows,stage)
        probe.freeze(PRIVATE/"SETTLED.json",dict(rows=rows,ledger=ledger))


def report(cards):
    saved=read(PRIVATE/"SETTLED.json")
    ledger=saved["ledger"]
    def key(r):
        return r["unit"]["stage"],r["request_sha256"],r["status"]
    actual=[read(p) for p in RUN.glob("*/visible/*/record.json")]
    if Counter(map(key,actual))!=Counter(map(key,ledger)):
        raise ValueError("Failed physical ledger reconciliation")
    rows=[]
    coverage=Counter()
    for r in saved["rows"]:
        coverage[f"{r['benchmark']}/{r['method']}/{r['disposition']}"]+=1
        rows.append(dict(case=r["uid"].split("/",1)[-1],benchmark=r["benchmark"],stratum=r["stratum"],
                         arm=r["method"],status=r["actor_status"],disposition=r["disposition"],
                         score=OLD["metric"](r),score_flags=r.get("score_flags"),
                         bias={k:r["score"].get(k) for k in ("OPB","UPB","FM")}
                              if r["benchmark"]=="RPEval" and r["score"] else None))
    print(json.dumps(dict(eligibility=coverage,rows=rows,physical=Counter(r["status"] for r in ledger),
                         stages=Counter(r["unit"]["stage"] for r in ledger),
                         tokens=sum((r["usage"] or {}).get("total_tokens",0) for r in ledger),
                         unknown_usage=sum("total_tokens" not in (r["usage"] or {}) for r in ledger),
                         retries=sum(r["automatic_retries"] for r in ledger)),indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["freeze","run","report"])
    action=parser.parse_args().action
    pin,cards,jobs=build()
    PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=PRIVATE/"FREEZE.json"
    if action=="freeze":
        probe.freeze(path,pin)
        print(Counter(c["source"]["benchmark"] for c in cards.values()))
    elif read(path)!=pin:
        raise ValueError("Frozen contrast protocol changed")
    elif action=="run":
        run(pin,cards,jobs)
    else:
        report(cards)
