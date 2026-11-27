"""Run two draws of three fixed RP Actor exposure policies on verified read-stage output."""
import json
import sys
from copy import deepcopy
from read_side import RUN, HERE, FORMAL, engine, probe, read, sha
from qamc.common import parse_object
from qamc_rpeval_terminal_judge_sensitivity import inspect

def subset(wire, indices):
    narrowed = deepcopy(wire)
    packet = json.loads(wire["messages"][1]["content"])
    if set(packet) != {"query","current_context","facts","source_evidence","preference_use_policy"}:
        raise ValueError("Unknown path for source re-injection")
    source = packet["source_evidence"]
    policies = packet["preference_use_policy"]
    if any(set(p)!={"memory_id","policy"} or p["policy"] not in ("A","B","C") for p in policies):
        raise ValueError("Policy has free text")
    if [p["memory_id"] for p in policies]!=[s["memory_id"] for s in source]:
        raise ValueError("Source-policy mismatch")
    if indices!=sorted(set(indices)) or not set(indices)<=set(range(len(source))):
        raise ValueError("Invalid subset")
    for key in ("source_evidence","preference_use_policy"):
        packet[key]=[packet[key][i] for i in indices]
    narrowed["messages"][1]["content"]=json.dumps(packet,ensure_ascii=False)
    return narrowed

def run(live):
    cards=read(HERE/"PANEL.json")
    parent=read(FORMAL/"PLAN.json")
    cases={c["uid"]:c for c in parent["cases"]}
    rp={r["uid"]:r for r in read(FORMAL/"RESULT_ROWS.json") if r["method"]=="RPR_PAPER_FULL"}
    reads=read(RUN/"READ_RESULTS.json")
    endpoints={r["uid"]:r for r in read(HERE.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    jobs, selection={},{}
    for card in cards:
        uid=card["uid"]
        raw=rp[uid]["actor_request"]
        if sha(raw)!=card["wire"] or cases[uid]["independent_confirmation"]:
            raise ValueError("Unverified source")
        packet=json.loads(raw["messages"][1]["content"])
        n=card["source_count"]
        if subset(raw,list(range(n)))!=raw:
            raise ValueError("Full wire changed")
        row=reads["rows"][uid]
        if row["status"]!="OK":
            selection[uid]={"status":row["status"]}
            continue
        chosen=row["positions"]
        if len(chosen) in (0,n):
            selection[uid]={"status":"UNCHANGED","positions":chosen}
            continue
        priority=sorted(range(n),key=lambda i:"CBA".index(packet["preference_use_policy"][i]["policy"]))
        same_count=sorted(priority[:len(chosen)])
        selection[uid]={"status":"CHANGED","pb":chosen,"rp":same_count}
        for arm,keep in (("FULL",list(range(n))),("PB",chosen),("RP_K",same_count)):
            wire=subset(raw,keep)
            remaining=wire["messages"][0]["content"]+json.dumps(
                {key:packet[key] for key in ("query","current_context","facts")},ensure_ascii=False)
            if any(s["text"] in remaining for i,s in enumerate(packet["source_evidence"]) if i not in keep):
                raise ValueError("Omitted source repeated elsewhere in visible input")
            jobs[uid,arm]=wire
    print("Verified Actor slots per draw:",len(jobs),flush=True)
    if not live:return
    engine.OUT=probe.OUT=probe.RUN=RUN
    ident={"experiment_sha256":sha([cards,reads,sha((HERE/"answers.py").read_bytes()),sha(parent)]),
           "service_reference_sha256":probe.read_reference()[1]}
    with probe.runner_lock(RUN/"runner.lock"):
        probe.freeze(RUN/"ANSWER_EXECUTION.json",ident)
        ledger=[]
        for rep in range(2):
            def stage(label,payload):
                name=f"{label}{rep}"
                engine.CAP[name]=36
                return engine.stage(name,payload,ident,True,ledger) if payload else {}
            actors=stage("Actor",jobs)
            judges=stage("Judge",{k:engine.rpe_wire(parent,cases[k[0]],{"uid":k[0],"actor_status":"OK","answer":r["answer"]})
                                 for k,r in actors.items() if r["status"]=="OK"})
            rows=[]
            for (uid,arm),actor in actors.items():
                judge=judges.get((uid,arm))
                status=(judge or actor)["status"]
                grade=flags=None
                if judge and status=="OK":
                    labels=endpoints[uid]["labels"]
                    try:
                        grade,_=probe.fields(parse_object(judge["answer"]),len(labels),True)
                        diagnostic=inspect({"uid":uid,"method":arm,"answer":actor["answer"],"native_fields":grade,
                                            "raw_scores":{"RPEvalJudge":judge["answer"]}},labels)
                        flags=diagnostic["flags"] if diagnostic else None
                        status="OK" if grade.get("match") else "INVALID_MATCH"
                    except (KeyError,TypeError,ValueError):
                        status="INVALID_SCORE"
                rows.append(dict(uid=uid,arm=arm,actor=actor,judge=judge,grade=grade,flags=flags,status=status))
            probe.freeze(RUN/f"DRAW{rep}.json",dict(selection=selection,rows=rows,ledger=list(ledger)))

if __name__=="__main__":
    if sys.argv[1:] not in (["check"],["run"]):raise SystemExit("check or run")
    run(sys.argv[1]=="run")
