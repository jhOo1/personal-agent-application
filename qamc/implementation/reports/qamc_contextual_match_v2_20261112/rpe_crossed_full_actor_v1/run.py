import json
from pathlib import Path
from collections import Counter
import cross_backbone as cb
from qamc.common import sha

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
OUT=HERE.parents[2]/"runs"/BASE.name/HERE.name/"private_v2"
read=cb.read

def main():
    old=BASE/"ipe_c_second_backbone_v1"
    panel=[r for r in read(old/"format_recovery/RESULTS.json")["rows"] if r["stratum"]=="contains_C"]
    assert len(panel)==8 and len({r["source_group"] for r in panel})==8
    manifests=[x for p in (old,old/"format_recovery") for x in read(p/"BackboneActor_MANIFEST.json")["units"] if x["unit"]["method"]=="RP_FULL"]
    gpt={x["unit"]["root_id"]:x["request"] for x in manifests}
    roots={r["uid"]:r for r in read(cb.v41.OUT/"FROZEN.json")["roots"]}
    reference={r["uid"]:r for r in read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    parent=read(cb.v41.formal.OUT/"PLAN.json")
    cases=cb.v41.author_cases(parent)
    jobs={};existing={};references={};labels={}
    for r in panel:
        uid=r["uid"];root=roots[uid];labels[uid]=r["labels"]
        q=root["archived_actor_request"];g=gpt[uid]
        assert sha(q)==root["archived_actor_sha256"] and sha(g)==r["actor"]["RP_FULL"]["request_sha256"]
        qview,gview=[json.loads(w["messages"][1]["content"]) for w in (q,g)]
        assert qview.keys()==gview.keys() and qview["source_evidence"]==gview["source_evidence"]
        assert all(qview[k]==gview[k] for k in root["public_task"])
        assert q["messages"][0]==g["messages"][0] and {k:v for k,v in q.items() if k not in ("model","messages")}=={k:v for k,v in g.items() if k not in ("model","messages")}
        existing[sha(q)]=reference[uid]["scores"]["RPR_PAPER_FULL"]
        existing[sha(g)]=r["scores"]["RP_FULL"]
        for policy,w in (("Q",q),("G",g)):
            for actor,model in (("Q",q["model"]),("G",g["model"])):
                wire=dict(w,model=model);key=uid,policy+actor
                jobs[key]=wire;references[key]=sha(wire)
    pin=dict(wires=sha(sorted((u,a,h) for (u,a),h in references.items())),code=sha(Path(__file__).read_bytes()),protocol=sha((HERE/"PROTOCOL.md").read_bytes()))
    OUT.mkdir(parents=True,exist_ok=True);cb.probe.freeze(OUT/"FROZEN.json",pin)
    cb.engine.OUT=cb.probe.OUT=OUT;cb.probe.RUN=OUT.parent
    ident=dict(experiment_sha256=sha(pin),service_reference_sha256=cb.probe.read_reference()[1])
    ledger=[]
    def call(stage,work):
        if not work:return {}
        cb.engine.CAP[stage]=len(work)
        return cb.engine.stage(stage,work,ident,True,ledger)
    with cb.probe.runner_lock(OUT.parent/"runner.lock"):
        new={k:w for k,w in jobs.items() if sha(w) not in existing}
        assert len({sha(w) for w in new.values()})==len(new)
        actors={}
        for alias in ("Q","G"):
            actors.update(call("CrossActor"+alias,{k:w for k,w in new.items() if k[1].endswith(alias)}))
        graders={k:cb.engine.rpe_wire(parent,cases[k[0]],{"uid":k[0],"actor_status":"OK","answer":v["answer"]}) for k,v in actors.items() if v["status"]=="OK" and v["answer"]}
        grades=call(cb.engine.RPE,graders)
        rows=[]
        for k,h in references.items():
            uid,a=k
            s=existing[h] if h in existing else cb.score_of(uid,a,grades.get(k),actors[k],labels[uid])
            rows.append(dict(uid=uid,arm=a,wire=h,origin="archive" if h in existing else "new",score=s))
        cb.probe.freeze(OUT/"SETTLED.json",dict(rows=rows,ledger=ledger))
        print("Assigned",len(rows),"new calls",len(ledger),Counter(r["status"] for r in ledger))
if __name__=="__main__":main()
