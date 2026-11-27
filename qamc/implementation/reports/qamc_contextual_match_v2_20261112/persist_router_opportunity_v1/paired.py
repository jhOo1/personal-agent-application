import json
from inventory import HERE, RUN, BASE, read, sha, persist, transfer, input_requests
from complete import get_author, select, actor_request, probe, engine
from trial import judge_wire
from repeat_receipts import branch

def main():
    roster=read(HERE.parent/"persist_author_controls_v2/PLAN.json")
    eligible=[r for r in read(HERE/"RESULTS.json")["outside"] if r["track"]!="beneficial_memory_usage" and r["observations"].get("style")]
    assert len(eligible)==1
    case,=[c for c in roster["cases"] if c["uid"].split("/")[-1].startswith(eligible[0]["prefix"]) and c["role"]=="DEV"]
    uid=case["uid"]
    task=persist.author.parent.smoke.task_for(case)
    public={"query":task.query,"memories":[m.text for m in task.memories]}
    assert sha(public)==case["public_sha256"]
    req=input_requests(case,public,read(transfer.OUT/"PLAN.json"))
    def answer(stage,wire):
        paths=list((BASE/"persist_performance_v1"/stage/"visible").glob("*/record.json"))
        p,=[p for p in paths if read(p)["unit"]["root_id"]==uid and read(p)["request_sha256"]==sha(wire)]
        assert read(p)["status"]=="OK" and read(p.parent/"request.json")==wire
        return read(p.parent/"response.json")["answer"]
    route=answer("QueryRoute",req["query"])
    mode=branch(public,route)
    assert mode=="style"
    evidence=select(case,public,route,answer("EvidenceSelect",req[mode]))
    assert 0<len(evidence)<len(public["memories"])
    proto=read(HERE.parents[2]/"reports/qamc_persistbench_actor_factorial/PLAN.json")
    actors={a:actor_request(case,task.query,mem,proto,proto["prompts"]["gepa"]) for a,mem in (("SELECTED",evidence),("FULL",public["memories"]))}
    assert all(w["max_tokens"]==8192 for w in actors.values())
    _,bounds,_=get_author()
    grade=judge_wire({uid:case},{uid:{"public":public}},roster["protocols"]["gpt41"],bounds)
    out=BASE/HERE.name/"private"
    out.mkdir(parents=True,exist_ok=True)
    pin=dict(code=sha((HERE/"paired.py").read_bytes()),protocol=sha((HERE/"PROTOCOL.md").read_bytes()),actors=sha(actors),scorer=sha(bounds[uid]))
    probe.freeze(out/"FROZEN.json",pin)
    engine.OUT=probe.OUT=out
    probe.RUN=out.parent
    ident=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    ledger=[]
    def call(name,jobs):
        if not jobs:return {}
        engine.CAP[name]=len(jobs)
        return engine.stage(name,{(uid,k):v for k,v in jobs.items()},ident,True,ledger)
    with probe.runner_lock(out.parent/"runner.lock"):
        replies=call("Actor",actors)
        wires={arm:grade(uid,v["answer"]) for (_,arm),v in replies.items() if v["status"]=="OK"}
        scores={}
        for j in ("GPT","Qwen"):
            jobs={a:(w if j=="GPT" else dict(w,model="qwen3.8-flash",max_tokens=8192)) for a,w in wires.items()}
            scores[j]={a:None for a in actors}
            for (_,a),r in call(j,jobs).items():
                if r["status"]=="OK":
                    try:scores[j][a]=persist.author.ext.parent.persist.score(case["category"],r["answer"])["rating"]
                    except (ValueError,KeyError,TypeError):pass
        result=dict(candidates=len(public["memories"]),selected=len(evidence),scores=scores,
                    request_count=len(ledger),statuses=[r["status"] for r in ledger],
                    unknown_usage=sum(not r.get("usage") for r in ledger),
                    tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger))
        probe.freeze(out/"SETTLED.json",dict(result=result,ledger=ledger))
        print(json.dumps(result))
if __name__=="__main__":main()
