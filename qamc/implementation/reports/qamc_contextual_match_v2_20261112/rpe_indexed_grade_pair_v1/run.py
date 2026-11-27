import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
import cross_backbone as cb
from qamc.common import sha

here = Path(__file__).resolve().parent
base = here.parent
out = here.parents[2]/"runs"/base.name/here.name/"private"
def main():
    rows=cb.read(base/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    actors={r["uid"]:r for r in cb.read(base/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json") if r["method"]=="RPR_PAPER_FULL"}
    parent=cb.read(cb.v41.formal.OUT/"PLAN.json")
    cases=cb.v41.author_cases(parent)
    pool=[]
    for r in rows:
        u=r["uid"]
        actor=actors[u]
        grade=r["scores"].get("RPR_PAPER_FULL") or {}
        if not actor.get("actor_request") or not (grade.get("grade") or {}).get("match"):
            continue
        view=json.loads(actor["actor_request"]["messages"][-1]["content"])
        policy=view["preference_use_policy"]
        if "".join(v["policy"] for v in policy)!=r["labels"]:
            continue
        assert sha(actor["answer"])==grade["answer_sha256"]
        pool.append((u,r["labels"],policy,grade))
    positives=[item for item in pool if set(item[1])!={"A"}]
    controls=sorted((item for item in pool if set(item[1])=={"A"}),key=lambda item:hashlib.sha256(item[0].encode()).digest())[:4]
    assert len(positives)==24 and len(controls)==4
    jobs={}
    items=sorted(positives+controls)
    for i,(u,labels,policy,grade) in enumerate(items):
        w=cb.engine.rpe_wire(parent,cases[u],{"uid":u,"actor_status":"OK","answer":actors[u]["answer"]})
        aug=deepcopy(w)
        aug["messages"][-1]["content"]+="\n\n原有 intent 的逐位索引（与原字符串相同）：\n"+"\n".join(f"第{j}条 ({p['memory_id']}) = {code}" for j,(p,code) in enumerate(zip(policy,labels),1))
        for arm in (("original","indexed") if i%2==0 else ("indexed","original")):
            jobs[u,arm]=w if arm=="original" else aug
    out.mkdir(parents=True,exist_ok=True)
    cb.engine.OUT=cb.probe.OUT=out
    cb.probe.RUN=out.parent
    ledger=[]
    with cb.probe.runner_lock(out.parent/"runner.lock"):
        hashes={"/".join(k):sha(v) for k,v in jobs.items()}
        cb.probe.freeze(out/"FROZEN.json",hashes)
        ident={"experiment_sha256":sha([hashes,sha((here/"PROTOCOL.md").read_bytes())]),"service_reference_sha256":cb.probe.read_reference()[1]}
        cb.engine.CAP[cb.engine.RPE]=len(jobs)
        replies=cb.engine.stage(cb.engine.RPE,jobs,ident,True,ledger)
        data=[]
        for u,labels,_,grade in items:
            new={a:cb.score_of(u,a,replies.get((u,a)),actors[u],labels) for a in ("original","indexed")}
            data.append(dict(uid=u,labels=labels,archive=grade,**new))
        cb.probe.freeze(out/"SETTLED.json",dict(rows=data,ledger=ledger))
if __name__=="__main__":
    main()
