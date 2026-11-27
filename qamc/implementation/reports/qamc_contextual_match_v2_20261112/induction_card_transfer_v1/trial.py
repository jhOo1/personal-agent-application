"""Hold original sources and the author final generator fixed across two card policies."""
import json
import sys
from copy import deepcopy
from card_inventory import HERE, BASE, ROOT, REPO, ABLATION, formal, MemAdapterBridge, git_blob
from qamc.contextual_match.memadapter_bridge import public_query
from qamc.common import parse_object, sha
from run_probe import engine,probe
from replay_panel import entry

RUN=engine.RUN.with_name(HERE.name)
OUT=RUN/"private"
SUMMARY=("Create a factual record of each supplied memory for another assistant. Preserve who said what, conditions, "
         "time, uncertainty and relevant details. Do not infer other situations or evaluate possible tasks. "
         'Return JSON {"memory_boundary_cards":[{"memory_id":"original ID","summary":"faithful record"},...]} '
         "with one record per input memory in order.")
def read(p):return json.loads(p.read_text())


def build():
    frozen=read(ROOT/"runs"/BASE.name/"shared_history_activation_v1/private/FROZEN.json")["assignments"]
    roster={u:s for u,s in frozen.items() if u.startswith("rpeval/")}
    b=MemAdapterBridge(REPO)
    rows={r["uid"]:r for r in read(formal.OUT/"RESULT_ROWS.json") if r["method"]=="MEMADAPTER_FULL" and r["uid"] in roster}
    inputs={}
    jobs={}
    for u,r in rows.items():
        task=formal.task_for({"uid":u})
        raw=r.get("reader_responses",{}).get("MemInduction")
        if not raw:continue
        try:cards=b.parse(task,"Stage1",raw)
        except (KeyError,TypeError,ValueError):continue
        wire=b.request(task,"Stage1")
        assert wire==r["reader_requests"]["MemInduction"] and cards==r["memory_boundary_cards"]
        control=deepcopy(wire)
        control["messages"]=[{"role":"system","content":SUMMARY},{"role":"user","content":json.dumps(b.memories(task),ensure_ascii=False,indent=2)}]
        jobs[u,"ordinary"]=control
        inputs[u]=(task,cards)
    assert len(roster)==18 and len(inputs)==16
    return roster,b,inputs,jobs


def main(mode):
    roster,b,inputs,jobs=build()
    raw_prompt=git_blob(REPO,ABLATION).decode()
    system,template=raw_prompt.split("USER PROMPT TEMPLATE")
    system=system.strip().removeprefix("SYSTEM PROMPT").strip()
    def actor(u,cards):
        task=inputs[u][0]
        values=b.functions["build_stage2_input"](current_query=public_query(task),memories=b.memories(task),boundary_cards=cards)
        body=b.functions["render_prompt"](template.strip(),values)
        return {"model":"qwen3.8-flash","temperature":0,"max_tokens":4096,"stream":True,"stream_options":{"include_usage":True},
                "messages":[{"role":"system","content":system},{"role":"user","content":body}]}
    actors={(u,"induction"):actor(u,cards) for u,(task,cards) in inputs.items()}
    pin={"roster":roster,"prep":{k[0]:sha(v) for k,v in jobs.items()},"actors":{k[0]:sha(v) for k,v in actors.items()},
         "implementation":sha((HERE/"trial.py").read_bytes()),"protocol":sha((HERE/"PROTOCOL.md").read_bytes())}
    OUT.mkdir(parents=True,exist_ok=True);probe.freeze(OUT/"FROZEN.json",pin)
    print("Assigned, valid archived induction, ordinary prepared:",len(roster),len(actors),len(jobs),flush=True)
    if mode=="freeze":return
    probe.RUN=RUN;engine.OUT=probe.OUT=OUT
    ident={"experiment_sha256":sha(pin),"service_reference_sha256":probe.read_reference()[1]}
    ledger=[]
    def stage(name,wires):
        if not wires:return {}
        engine.CAP[name]=len(wires)
        return engine.stage(name,wires,ident,True,ledger)
    with probe.runner_lock(RUN/"runner.lock"):
        summaries=stage("Record",jobs)
        for (u,a),reply in summaries.items():
            if reply["status"]!="OK":continue
            try:
                obj=parse_object(reply["answer"]);records=obj["memory_boundary_cards"]
                assert [r["memory_id"] for r in records]==[m.memory_id for m in inputs[u][0].memories]
                assert all(set(r)=={"summary","memory_id"} and isinstance(r["summary"],str) and r["summary"].strip() for r in records)
            except (AssertionError,KeyError,TypeError,ValueError):continue
            actors[u,a]=actor(u,{"memory_boundary_cards":records})
        answers=stage("Actor",actors)
        parent=read(formal.OUT/"PLAN.json"); cases={c["uid"]:c for c in parent["cases"]}
        grades=stage("Native",{k:engine.rpe_wire(parent,cases[k[0]],{"uid":k[0],"actor_status":"OK","answer":v["answer"]})
                            for k,v in answers.items() if v["status"]=="OK"})
        archived={r["uid"]:r for r in read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
        result=[]
        for (u,a),v in answers.items():
            reply=grades.get((u,a),{});fields={}
            raw=reply.get("answer") if reply.get("status")=="OK" else None
            if raw:
                try:fields,_=probe.fields(parse_object(raw),len(archived[u]["labels"]),True)
                except (TypeError,ValueError,KeyError):pass
            score=entry(archived[u],v.get("answer"),fields,raw,archived[u]["labels"])
            result.append({"uid":u,"arm":a,"score":score})
        probe.freeze(OUT/"RESULTS.json",{"rows":result,"ledger":ledger})


if __name__=="__main__":
    if sys.argv[1:] not in (["freeze"],["run"]):raise SystemExit("freeze|run")
    main(sys.argv[1])
