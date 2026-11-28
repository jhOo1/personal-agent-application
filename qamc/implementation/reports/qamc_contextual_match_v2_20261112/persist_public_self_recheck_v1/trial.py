import ast
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

from check_exposure_fr3 import prepare, judge_wire
from complete import actor_request, engine, probe
from qamc.common import sha
from transfer_replay import persist

here=Path(__file__).resolve().parent
runs=here.parents[2]/"runs"/here.parent.name
out=runs/here.name
up=runs/"persist_memadapter_release_v1/upstream"
read=lambda p:json.loads(p.read_text())
rev="6b517dc90d4c7e0ebc4d2305684d45051f792cc9"

def released():
    def source(name):
        return subprocess.check_output(["git","-C",up,"show",f"{rev}:methods/shared/{name}"],text=True)
    text=source("prompts.py")
    prompt=next(ast.literal_eval(n.value) for n in ast.parse(text).body if isinstance(n,ast.Assign)
                and n.targets[0].id=="SELF_RECHECK")
    tree=ast.parse(source("run_extra_interventions.py"))
    # Exact pinned pure parser without importing the authors' model stack.
    parser=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="parse_selected_ids")
    scope={"json":json}
    exec(compile(ast.Module(body=[parser],type_ignores=[]),"<released-ID-parser>","exec"),scope)
    return prompt,scope["parse_selected_ids"]

def main():
    prompt, parse=released()
    cases, inputs, protocol, judge, bounds=prepare()
    make_grade=judge_wire(cases,inputs,judge,bounds)
    previous={(r["uid"],r["repeat"]):r for f in sorted((runs/"persist_exposure_fr3_v1").glob("*_SETTLED.json"))
              for r in read(f)["rows"]}
    assert len(cases)==49 and len(previous)==111
    qold={}
    for r in read(runs/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"]:
        if r["wire"]: qold[r["uid"],r["repeat"],r["wire"]]=r["qwen"]
    memories={u:[dict(memory_id=f"memory_{i:02d}",content=t) for i,t in enumerate(v["public"]["memories"],1)]
              for u,v in inputs.items()}
    wires={u:persist.author.ext.text_request(prompt,json.dumps(dict(question=v["public"]["query"],
           retrieved_memories=memories[u]),ensure_ascii=False),"qwen3.8-flash",8192) for u,v in inputs.items()}
    pin=dict(rev=rev,code=sha(Path(__file__).read_bytes()),protocol=sha((here/"PROTOCOL.md").read_bytes()),
             selectors={u:sha(v) for u,v in wires.items()},prior=sha(sorted(previous.items())),qwen=sha(sorted(qold.items())))
    probe.RUN=out
    engine.OUT=probe.OUT=out/"private"
    probe.OUT.mkdir(parents=True,exist_ok=True)
    probe.freeze(out/"FROZEN.json",pin)
    if sys.argv[1]=="freeze":return
    assert sys.argv[1]=="run"
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    scorer=persist.author.ext.parent.persist
    for n in (1,2,3):
        dest=out/f"DRAW_{n}.json"
        with probe.runner_lock(out/"runner.lock"):
            if dest.exists():continue
            ledger=[]
            def stage(label,jobs):
                name=f"D{n}{label}"
                engine.CAP[name]=len(jobs)
                ret=engine.stage(name,{(u,"direct"):w for u,w in jobs.items()},identity,True,ledger) if jobs else {}
                return {u:v for (u,_),v in ret.items()}
            uids=sorted(u for u,rep in previous if rep==n)
            selected=stage("Select",{u:wires[u] for u in uids})
            cells={u:dict(uid=u,repeat=n,track=cases[u]["category"],select=selected[u]["status"],
                          actor="NO_UPSTREAM",gpt=None,qwen=None) for u in uids}
            jobs,actors={},{}
            for u,r in selected.items():
                if r["status"]!="OK":continue
                try:
                    ids=parse(r["answer"],memories[u],partition=False)
                    declared=json.loads(r["answer"])
                except (ValueError,KeyError,TypeError,AttributeError):
                    cells[u]["select"]="INVALID_ID_RESPONSE"
                    continue
                cells[u].update(ids=ids,field_present="keep_memory_ids" in declared)
                src=[m["content"] for m in memories[u] if m["memory_id"] in ids]
                wire=actor_request(cases[u],inputs[u]["public"]["query"],src,protocol,protocol["prompts"]["gepa"])
                cache={c["actor"]["request_sha256"]:c["actor"] for c in previous[u,n]["methods"].values() if c.get("actor")}
                if sha(wire) in cache:actors[u]=cache[sha(wire)]
                else:jobs[u]=wire
            actors.update(stage("Actor",jobs))
            for label in ("gpt","qwen"):
                jobs={}
                for u,a in actors.items():
                    cells[u]["actor"]=a["status"]
                    if a["status"]!="OK":continue
                    cells[u]["answer_hash"]=sha(a["answer"])
                    wire=make_grade(u,a["answer"])
                    if label=="qwen":
                        wire=dict(wire,model="qwen3.8-flash",max_tokens=8192)
                        key=(u,n,sha(wire))
                        if key in qold:
                            cells[u][label]=qold[key]
                            continue
                    else:
                        existing=[c for c in previous[u,n]["methods"].values() if c.get("judge") and c["judge"]["request_sha256"]==sha(wire)]
                        if existing:
                            score=existing[0]["score"]
                            cells[u][label]=score["rating"] if score else None
                            continue
                    jobs[u]=wire
                for u,rep in stage(label,jobs).items():
                    if rep["status"]=="OK":
                        try:cells[u][label]=scorer.score(cells[u]["track"],rep["answer"])["rating"]
                        except (KeyError,TypeError,ValueError):pass
            probe.freeze(dest,dict(rows=list(cells.values()),ledger=ledger))
            print("Settled",n,len(cells),Counter(r["status"] for r in ledger),flush=True)
if __name__=="__main__": main()
