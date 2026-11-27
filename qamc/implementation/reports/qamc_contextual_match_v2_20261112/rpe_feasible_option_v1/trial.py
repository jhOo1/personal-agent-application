"""Frozen end-to-end test of supporting preferences as a feasible-option tie breaker."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
from run_probe import probe, engine
from qamc.common import parse_object, sha

here=Path(__file__).resolve().parent
base=here.parent
def read(p):return json.loads(p.read_text())
panel=read(base/"ipe_c_rate_matched_controls_v1/../selective_path_frontier_v1/RESULTS.json")["rows"]
source={r["uid"]:r for r in read(base/"counterfactual_rpeval_v41/FROZEN.json")["roots"]}
archive={r["uid"]:r for r in read(base/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
extras={
"generic":"Deliver a practical, concrete answer. Check that the plan fits the request, respects applicable requirements, and offers useful recommendations in an appropriate level of detail.",
"feasible":"Choose options that already meet the current task and its applicable hard constraints. Within those feasible options, use a supporting preference to choose between concrete alternatives for the person whose decision it is. Leave the shared default alone when only a personal choice is affected."}
picked={}; groups=set()
for stratum,limit in (("soft",4),("ignore",2),("hard",2)):
    n=0
    for r in sorted(panel,key=lambda x:sha(["feasible-options-v1",x["uid"]])):
        u=r["uid"]; lab=archive[u]["labels"]
        if ("hard" if "C" in lab else "soft" if "B" in lab else "ignore")!=stratum or r["source_group"] in groups:continue
        picked[u]=stratum;groups.add(r["source_group"]);n+=1
        if n==limit:break
    assert n==limit
jobs={}
for u in picked:
    orig=source[u]["archived_actor_request"]
    assert sha(orig)==source[u]["archived_actor_sha256"] and orig["model"]=="qwen3.8-flash"
    for arm,extra in extras.items():
        w=deepcopy(orig);w["messages"][0]["content"]+="\n"+extra;jobs[u,arm]=w
run=here.parents[2]/"runs"/base.name/here.name
out=run/"private";out.mkdir(parents=True,exist_ok=True)
probe.RUN,probe.OUT,engine.OUT=run,out,out
with probe.runner_lock(run/"runner.lock"):
    pin=dict(panel=picked,code=sha(Path(__file__).read_bytes()),protocol=sha((here/"PROTOCOL.md").read_bytes()),actor_hashes=sorted(map(sha,jobs.values())))
    probe.freeze(out/"FROZEN.json",pin)
    identity=dict(experiment_sha256=sha(pin),service_reference_sha256=probe.read_reference()[1])
    ledger=[]
    def stage(name,wires):
        engine.CAP[name]=len(wires)
        return engine.stage(name,dict(sorted(wires.items(),key=lambda kv:sha(kv[0]))),identity,True,ledger)
    parent=read(engine.transport.formal.OUT/"PLAN.json");cases=engine.transport.author_cases(parent)
    answers=stage("FeasibleActor",jobs)
    grades=stage("FeasibleGrade",{(u,a):engine.rpe_wire(parent,cases[u],dict(uid=u,actor_status="OK",answer=r["answer"])) for (u,a),r in answers.items() if r["status"]=="OK"})
    rows=[]
    for u in picked:
        cell=dict(uid=u,stratum=picked[u],methods={k:archive[u]["scores"][k]["grade"] for k in ("IPE_C","TASK_ONLY","RPR_PAPER_FULL")})
        for a in extras:
            rec=grades.get((u,a),{})
            g={}
            if rec.get("status")=="OK":
                try:g,_=probe.fields(parse_object(rec["answer"]),len(archive[u]["labels"]),True)
                except (KeyError,TypeError,ValueError):pass
            cell["methods"][a]=g
        rows.append(cell)
    result=dict(rows=rows,requests=len(ledger),statuses=dict(Counter((r["unit"]["stage"]+"/"+r["status"]) for r in ledger)),reported_tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),unknown_usage=sum(not r.get("usage") for r in ledger))
    probe.freeze(out/"SETTLED.json",result)
