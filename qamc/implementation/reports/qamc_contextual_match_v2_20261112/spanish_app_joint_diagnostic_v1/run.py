"""One score-bearing diagnostic cell, using the existing journal."""
import json
import sys
from pathlib import Path
from copy import deepcopy
import run_authority as engine
from qamc.common import sha

here = Path(__file__).resolve().parent
probe = engine.probe
root, = [r for r in probe.read(here.parent/"counterfactual_rpeval_v41/FROZEN.json")["roots"]
         if r["uid"]=="rpeval/formal_multi_v1/implicit/067"]
uid=root["uid"]
request = deepcopy(root["archived_actor_request"])
assert sha(request)==root["archived_actor_sha256"]
payload=json.loads(request["messages"][-1]["content"])
for key in ("source_evidence","preference_use_policy"):
    payload[key]=[s for s in payload[key] if s["memory_id"] in ("M1","M3")]
request["messages"][-1]["content"]=json.dumps(payload,ensure_ascii=False)
assert sha(request)=="fe81de16aca66b50791471697b70a860e223781f7288a67dec679e20bc89aac7"
engine.OUT=probe.OUT=here
probe.RUN=engine.RUN.with_name(here.name)
engine.CAP={"JointActor":1,engine.RPE:1}
live=sys.argv[1]=="run"
plan={"service_reference_sha256":probe.read_reference()[1],"request_sha256":sha(request)}
ledger=[]
def stage(name,jobs,cache=None):
    return engine.stage(name,jobs,plan,live,ledger,cache)
with probe.runner_lock(probe.RUN/"runner.lock"):
    if live:
        probe.freeze(here/"EXECUTION.json",plan)
    assert probe.read(here/"EXECUTION.json")==plan
    actor=stage("JointActor",{(uid,"JOINT"):request})[uid,"JOINT"]
    row={"uid":uid,"method":"JOINT","actor_status":actor["status"],"answer":actor["answer"],"score":None}
    engine.grade_rpe({uid:root},[row],stage)
    result={"row":row,"ledger":ledger}
    if live:
        probe.freeze(probe.RUN/"RESULTS.json",result)
    assert probe.read(probe.RUN/"RESULTS.json")==result
    print(row["score"],[r["status"] for r in ledger],sum((r["usage"] or {}).get("total_tokens",0) for r in ledger))
