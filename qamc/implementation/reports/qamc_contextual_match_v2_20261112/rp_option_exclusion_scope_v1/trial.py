import json
import sys
from copy import deepcopy
from pathlib import Path
from qamc.common import sha, parse_object
import qamc_rpeval_formal_multi_run as formal
from run_probe import engine,probe
from replay_panel import entry

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RUN=engine.RUN.with_name(HERE.name)
OUT=RUN/"private"
def read(path):
    return json.loads(path.read_text())

DIAGNOSTIC = {"rpeval/formal_multi_v1/explicit/132","rpeval/formal_multi_v1/explicit/057"}
INSTRUCTIONS = {
    "ordinary": "Before delivering the answer, check that the options recommended are practical, specific and justified for the current request. Preserve applicable preferences and constraints. Remove unnecessary repetition. Return only the final answer.",
    "scope": "When a preference changes your recommendation, check each option you would reject: which exact property of that option violates the relevant memory, for whom, and under what condition? Reject it only when the property applies; when an option has versions with and without that property, qualify the version rather than excluding the whole category. Preserve binding constraints in every concrete recommendation. State a constraint once where useful and put the remaining detail into the choices. Return only the final answer.",
}

def prepare():
    index={r["uid"]:r for r in read(formal.OUT/"RESULT_ROWS.json") if r["method"]=="RPR_PAPER_FULL"}
    rows=read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    old={k.split("|")[0] for k in read(RUN.parent/"des2gen_suppressed_visibility_v1/private/FROZEN.json")["wires"]}
    excluded={r["source_group"] for r in rows if r["uid"] in old}
    groups=set()
    wires={}
    for r in sorted(rows,key=lambda row:(row["uid"] not in DIAGNOSTIC,sha([HERE.name,row["uid"]]))):
        u=r["uid"]
        if r["old_route"]!="REUSE_RP" or r["source_group"] in groups:continue
        if u not in DIAGNOSTIC and r["source_group"] in excluded:continue
        ref=index[u]
        wire=ref.get("actor_request")
        if not wire:continue
        assert sha(wire)==ref["actor_request_sha256"]
        for arm,extra in INSTRUCTIONS.items():
            altered=deepcopy(wire)
            assert altered["messages"][0]["role"]=="system"
            altered["messages"][0]["content"]+="\n\n"+extra
            wires[u,arm]=altered
        groups.add(r["source_group"])
        if len(groups)==16:break
    assert len(groups)==16 and all((u,"scope") in wires for u in DIAGNOSTIC)
    return wires

def main(mode):
    wires=prepare()
    pin={"wires":{u+"|"+a:sha(v) for (u,a),v in wires.items()},"protocol":sha((HERE/"PROTOCOL.md").read_bytes()),"code":sha((HERE/"trial.py").read_bytes())}
    OUT.mkdir(parents=True,exist_ok=True)
    probe.freeze(OUT/"FROZEN.json",pin)
    print(len(wires),"frozen Actor requests",flush=True)
    if mode=="freeze":return
    assert mode=="run"
    probe.RUN=RUN;engine.OUT=probe.OUT=OUT
    ident={"experiment_sha256":sha(pin),"service_reference_sha256":probe.read_reference()[1]}
    ledger=[]
    with probe.runner_lock(RUN/"runner.lock"):
        engine.CAP["Actor"]=len(wires)
        answers=engine.stage("Actor",wires,ident,True,ledger)
        plan=read(formal.OUT/"PLAN.json")
        cases={c["uid"]:c for c in plan["cases"]}
        judges={k:engine.rpe_wire(plan,cases[k[0]],{"uid":k[0],"actor_status":"OK","answer":v["answer"]}) for k,v in answers.items() if v["status"]=="OK"}
        engine.CAP["Native"]=len(wires)
        grades=engine.stage("Native",judges,ident,True,ledger) if judges else {}
        prior={r["uid"]:r for r in read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
        results=[]
        for (u,a),v in answers.items():
            reply=grades.get((u,a),{})
            raw=reply.get("answer") if reply.get("status")=="OK" else None
            fields={}
            if raw:
                try:fields,_=probe.fields(parse_object(raw),len(prior[u]["labels"]),True)
                except (KeyError,ValueError,TypeError):pass
            score=entry(prior[u],v.get("answer"),fields,raw,prior[u]["labels"])
            results.append({"uid":u,"arm":a,"score":score})
        probe.freeze(OUT/"RESULTS.json",{"rows":results,"ledger":ledger})
if __name__=="__main__":main(sys.argv[1])
