import json
import sys
from pathlib import Path
from qamc.common import sha
from check_exposure_fr3 import prepare, judge_wire
from complete import engine,probe,select,actor_request
from repeat_receipts import branch
from transfer_replay import persist

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[2]/"runs"/HERE.parent.name/HERE.name/"private"
def main():
    cases,items,protocol,judge,bounds=prepare()
    ids=sorted(u for u,c in cases.items() if c["category"]=="beneficial_memory_usage")
    assert len(ids)==18 and len({cases[u]["group_id"] for u in ids})==18
    pin=dict(inputs={u:sha(items[u]) for u in ids},code=sha((HERE/"trial.py").read_bytes()),
             protocol=sha((HERE/"PROTOCOL.md").read_bytes()),judge=sha(judge),generation=sha(protocol["prompts"]))
    OUT.mkdir(parents=True,exist_ok=True)
    probe.freeze(OUT/"FROZEN.json",pin)
    print("Fresh registered utility roots:",len(ids),flush=True)
    if sys.argv[1]=="freeze":return
    assert sys.argv[1]=="run"
    engine.OUT=probe.OUT=OUT;probe.RUN=OUT.parent
    ident=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    ledger=[]
    def call(stage,jobs):
        if not jobs:return {}
        # Requests are joined by exact wire within this replicate.
        by_hash={sha(w):w for w in jobs.values()}
        engine.CAP[stage]=len(by_hash)
        replies=engine.stage(stage,{(h,"replicate"):w for h,w in by_hash.items()},ident,True,ledger)
        return {k:replies[sha(w),"replicate"] for k,w in jobs.items()}
    grade=judge_wire(cases,items,judge,bounds)
    marks={}
    with probe.runner_lock(OUT.parent/"runner.lock"):
        routes=call("Route",{u:items[u]["selection_requests"]["query"] for u in ids})
        select_jobs={}
        for u,v in routes.items():
            if v["status"]=="OK":
                try:key=branch(items[u]["public"],v["answer"])
                except (KeyError,TypeError,ValueError):continue
                select_jobs[u]=items[u]["selection_requests"][key]
        selected=call("Select",select_jobs)
        actors={(u,a):items[u][a] for u in ids for a in ("FULL","RUBRIC")}
        for u,v in selected.items():
            if v["status"]!="OK":continue
            task=items[u]["public"]
            try:e=select(cases[u],task,routes[u]["answer"],v["answer"])
            except (ValueError,KeyError,TypeError):continue
            marks[u]=len(e)
            actors[u,"SELECTED"]=actor_request(cases[u],task["query"],e,protocol,protocol["prompts"]["gepa"])
        replies=call("Actor",actors)
        wires={k:grade(k[0],v["answer"]) for k,v in replies.items() if v["status"]=="OK" and v.get("answer")}
        grades={j:call(j,{k:(w if j=="GPT" else dict(w,model="qwen3.8-flash",max_tokens=8192)) for k,w in wires.items()}) for j in ("GPT","Qwen")}
        rows=[]
        for u in ids:
            for a in ("SELECTED","FULL","RUBRIC"):
                k=u,a
                row=dict(uid=u,arm=a,selection_count=marks.get(u),delivered=k in wires)
                for j,rs in grades.items():
                    g=rs.get(k,{})
                    row[j]=None
                    if g.get("status")=="OK":
                        try:row[j]=persist.author.ext.parent.persist.score(cases[u]["category"],g["answer"])["rating"]
                        except (ValueError,TypeError,KeyError):pass
                rows.append(row)
        probe.freeze(OUT/"SETTLED.json",dict(rows=rows,ledger=ledger))
if __name__=="__main__":main()
