"""Complete the scorer bridge on the two remaining published risk epochs."""
import json
from collections import defaultdict
from pathlib import Path
from qamc.common import sha
from check_exposure_fr3 import prepare, judge_wire
from complete import engine, probe
from transfer_replay import persist

here = Path(__file__).resolve().parent
root = here.parents[2]
runs = root/"runs"/here.parent.name
previous = runs/"persist_released_grade_agreement_v1/private"
run = runs/here.name
def read(path):
    return json.loads(path.read_text())

def main():
    old = read(previous/"SETTLED.json")["rows"]
    old = {(r["root"],r["model"]):r for r in old if r["category"]!="beneficial_memory_usage"}
    assert len(old)==30
    release=(root/"literature/qamc_pa_v1/PersistBench/experiments/multi_turn/paper_traces/baseline_all_models.json").read_bytes()
    pin=read(previous/"FROZEN.json")
    assert sha(release)==pin["release"]
    frozen={(u,m):h for u,m,h in pin["wires"]}
    cases,items,_,judge,bounds=prepare()
    wire=judge_wire(cases,items,judge,bounds)
    jobs,labels={},{}
    for e in json.loads(release)["entries"].values():
        task={k:e[k] for k in ("query","memories")}
        uid="persistbench/"+sha(task)[:20]
        if uid not in {u for u,m in old}:
            continue
        assert task==items[uid]["public"]
        for name,model in e["results"].items():
            m=name.replace("/","_")
            assert len(model["generations"])==3
            for i,g in enumerate(model["generations"]):
                assert g["generation_index"]==i and not g["error"]
                w=wire(uid,g["memory_response"])
                if i==0:
                    assert sha(w)==frozen[uid,m] and int(g["judge"]["score"])==old[uid,m]["released"]
                else:
                    key=(uid,f"{m}@{i}")
                    jobs[key]=w
                    labels[key]=(m,i,int(g["judge"]["score"]))
    assert len(jobs)==60
    probe.RUN=run
    probe.OUT=engine.OUT=run/"private"
    probe.OUT.mkdir(parents=True,exist_ok=True)
    lock=dict(release=pin["release"],wires=sorted(sha(w) for w in jobs.values()),protocol=sha((here/"PROTOCOL.md").read_bytes()))
    with probe.runner_lock(run/"runner.lock"):
        probe.freeze(probe.OUT/"FROZEN.json",lock)
        ledger=[]
        engine.CAP["RiskGrade"]=60
        replies=engine.stage("RiskGrade",jobs,dict(experiment_sha256=sha(lock),service_reference_sha256=probe.read_reference()[1]),True,ledger)
        rows=[dict(r,draw=0) for r in old.values()]
        for k,r in replies.items():
            m,i,official=labels[k]
            category=old[k[0],m]["category"]
            score=None
            if r["status"]=="OK":
                try:
                    score=persist.author.ext.parent.persist.score(category,r["answer"])["rating"]
                except (ValueError,KeyError,TypeError):
                    pass
            rows.append(dict(root=k[0],model=m,draw=i,released=official,project=score,category=category))
        probe.freeze(probe.OUT/"SETTLED.json",dict(rows=rows,ledger=ledger))
if __name__=="__main__":
    main()
