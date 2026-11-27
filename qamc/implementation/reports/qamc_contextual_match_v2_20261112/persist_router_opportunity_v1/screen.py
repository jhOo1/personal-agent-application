from collections import Counter,defaultdict
from inventory import HERE, BASE, read, sha, persist, transfer, input_requests
from complete import probe, engine
from repeat_receipts import branch
import json

def run():
    roster=read(HERE.parent/"persist_author_controls_v2/PLAN.json")
    prefixes={r["prefix"] for r in read(HERE/"RESULTS.json")["outside"] if not r["observations"]}
    plan=read(transfer.OUT/"PLAN.json")
    tasks={};jobs={};tracks={}
    for c in roster["cases"]:
        u=c["uid"]
        if u.split("/")[-1][:8] not in prefixes:continue
        assert c["role"]=="DEV"
        t=persist.author.parent.smoke.task_for(c)
        tasks[u]=dict(query=t.query,memories=[m.text for m in t.memories])
        assert sha(tasks[u])==c["public_sha256"]
        jobs[u,"screen"]=input_requests(c,tasks[u],plan)["query"]
        tracks[u]=c["category"]
    assert len(jobs)==10 and Counter(tracks.values())=={"sycophancy":8,"beneficial_memory_usage":2}
    out=BASE/HERE.name/"screen_private";out.mkdir(parents=True,exist_ok=True)
    pin=dict(jobs=sha(sorted((u,sha(w)) for (u,_),w in jobs.items())),code=sha((HERE/"screen.py").read_bytes()),protocol=sha((HERE/"SCREEN.md").read_bytes()))
    probe.freeze(out/"FROZEN.json",pin)
    engine.OUT=probe.OUT=out;probe.RUN=out;engine.CAP["QueryOnly"]=len(jobs)
    ledger=[];counts=defaultdict(Counter);roots={}
    with probe.runner_lock(out/"runner.lock"):
        replies=engine.stage("QueryOnly",jobs,dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1]),True,ledger)
        for (u,_),r in replies.items():
            mode="missing"
            if r["status"]=="OK":
                try:mode=branch(tasks[u],r["answer"])
                except (ValueError,TypeError,KeyError):mode="invalid"
            counts[tracks[u]][mode]+=1;roots[u]=mode
        res=dict(counts=counts,requests=len(ledger),statuses=Counter(r["status"] for r in ledger),tokens=sum((r["usage"] or {}).get("total_tokens",0) for r in ledger),unknown_usage=sum(not r["usage"] for r in ledger))
        probe.freeze(out/"SETTLED.json",dict(result=res,ledger=ledger,roots=roots));print(json.dumps(res))
if __name__=="__main__":run()
