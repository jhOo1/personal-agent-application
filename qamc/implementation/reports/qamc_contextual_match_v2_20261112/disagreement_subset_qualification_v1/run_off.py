"""Fixed OFF-branch contestant versus same-count RP with identical prompt and fused labels."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/"rpe_pb_on_transfer_v1"))
from answers import subset
from read_side import engine, probe, read, sha, FORMAL, RUN as previous_run

def prepare():
    endpoints = read(HERE.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    ranks = {r["uid"]:r["policies"] for r in read(FORMAL/"RPR_RANK_FUSION_AUDIT_300.json")["rows"]}
    full = {r["uid"]:r for r in read(FORMAL/"RESULT_ROWS.json") if r["method"]=="RPR_PAPER_FULL"}
    parent = read(FORMAL/"PLAN.json")
    cases = {r["uid"]:r for r in parent["cases"]}
    jobs = {}
    for row in endpoints:
        if not all(v["grade"].get("match") for v in row["scores"].values()):
            continue
        uid = row["uid"]
        policies = ranks[uid]
        ipe,mle,fused = [policies[k]["policy"] for k in ("IPE_ONLY","MLE_ONLY","PAPER_FUSION")]
        assert not cases[uid]["independent_confirmation"]
        if "C" in ipe:
            continue
        selected = [i for i,(a,b) in enumerate(zip(ipe,mle)) if a=="B" and b=="C"]
        if not selected:
            continue
        wire = full[uid]["actor_request"]
        assert sha(wire)==policies["PAPER_FUSION"]["actor_request_sha256"]
        packet = json.loads(wire["messages"][1]["content"])
        assert "".join(p["policy"] for p in packet["preference_use_policy"])=="".join(fused)
        ordered = sorted(range(len(fused)),key=lambda i:"CBA".index(fused[i]))
        for arm,idx in (("DISAGREE",selected),("RP_K",sorted(ordered[:len(selected)]))):
            jobs[uid,arm]=subset(wire,idx)
    assert len(jobs)==48
    return jobs,parent,cases

def main(action):
    jobs,parent,cases = prepare()
    pin = {uid+"/"+arm:sha(wire) for (uid,arm),wire in sorted(jobs.items())}
    if action=="manifest":
        print(json.dumps(pin,indent=2,sort_keys=True))
        return
    assert pin==read(HERE/"ACTOR_HASHES.json")
    run = previous_run.with_name(HERE.name)
    engine.OUT=probe.OUT=probe.RUN=run
    run.mkdir(parents=True,exist_ok=True)
    ident = {"experiment_sha256":sha([pin,(HERE/"PROTOCOL.md").read_text(),(HERE/"run_off.py").read_text()]),
             "service_reference_sha256":probe.read_reference()[1]}
    with probe.runner_lock(run/"runner.lock"):
        probe.freeze(run/"EXECUTION.json",ident)
        engine.CAP={"Actor":48,"Judge":48}
        ledger=[]
        actors=engine.stage("Actor",jobs,ident,True,ledger)
        grades={k:engine.rpe_wire(parent,cases[k[0]],{"uid":k[0],"actor_status":"OK","answer":r["answer"]})
                for k,r in actors.items() if r["status"]=="OK"}
        scored=engine.stage("Judge",grades,ident,True,ledger) if grades else {}
        probe.freeze(run/"RESULTS.json",{"rows":[{"uid":k[0],"arm":k[1],"actor":r,"judge":scored.get(k)}
            for k,r in actors.items()],"ledger":ledger})

if __name__=="__main__":
    if sys.argv[1:] not in (["manifest"],["run"]):raise SystemExit("manifest or run")
    main(sys.argv[1])
