from copy import deepcopy
from pathlib import Path
import hashlib
import json
import cross_backbone as cb
from qamc.common import sha

here=Path(__file__).resolve().parent
base=here.parent
run=here.parents[2]/"runs"/base.name/here.name
out=run/"private"
prompts={
    "review":"先形成对当前请求有帮助的完整回答，再检查每条建议的相关性、准确性和可操作性。依据提供的使用策略处理历史偏好，兼顾当前要求、适用条件和任务完整性。只输出自然、可直接使用的最终回答。",
    "screen":"先从当前请求形成可行选项。对于标为 C 的历史，若是当前参与者的明确硬条件，逐项淘汰违反条件的选项，并以可行选项替换；若是正向喜好，用它排序而不凭空制造禁令。在余下选项中落实适用的 B。只输出自然、可直接使用的最终回答。"
}

def main():
    rows=cb.read(base/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    actors={r["uid"]:r for r in cb.read(base/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json") if r["method"]=="RPR_PAPER_FULL"}
    cases=cb.v41.author_cases(parent:=cb.read(cb.v41.formal.OUT/"PLAN.json"))
    chosen={}
    for r in sorted(rows,key=lambda r:hashlib.sha256(r["uid"].encode()).digest()):
        u=r["uid"]; a=actors[u]
        old=r["scores"].get("RPR_PAPER_FULL") or {}
        if r["old_route"]!="REUSE_RP" or not a.get("actor_request") or not (old.get("grade") or {}).get("match"):
            continue
        w=a["actor_request"]
        if not any(v["policy"]=="C" for v in json.loads(w["messages"][-1]["content"])["preference_use_policy"]):
            continue
        if r["source_group"] in chosen:continue
        assert sha(w)==a["actor_request_sha256"] and sha(a["answer"])==old["answer_sha256"]
        chosen[r["source_group"]]=r
        if len(chosen)==8:break
    assert len(chosen)==8
    jobs={}
    for r in chosen.values():
        u=r["uid"]
        for k,p in prompts.items():
            w=deepcopy(actors[u]["actor_request"]);w["messages"][0]["content"]+="\n\n"+p
            jobs[u,k]=w
    out.mkdir(parents=True,exist_ok=True)
    cb.probe.RUN=run;cb.engine.OUT=cb.probe.OUT=out
    with cb.probe.runner_lock(run/"runner.lock"):
        frozen={u+"/"+k:sha(w) for (u,k),w in jobs.items()}
        cb.probe.freeze(out/"FROZEN.json",frozen)
        ident={"experiment_sha256":sha([frozen,sha((here/"PROTOCOL.md").read_bytes())]),"service_reference_sha256":cb.probe.read_reference()[1]}
        ledger=[]
        def stage(name,batch):
            cb.engine.CAP[name]=len(batch)
            return cb.engine.stage(name,batch,ident,True,ledger) if batch else {}
        answers=stage("Actor",jobs)
        graders={k:cb.engine.rpe_wire(parent,cases[k[0]],{"uid":k[0],"actor_status":"OK","answer":v["answer"]}) for k,v in answers.items() if v["status"]=="OK" and v["answer"]}
        grades=stage(cb.engine.RPE,graders)
        result=[]
        for r in chosen.values():
            u=r["uid"]
            result.append(dict(uid=u,reference=r["scores"]["RPR_PAPER_FULL"],**{k:cb.score_of(u,k,grades.get((u,k)),answers[u,k],r["labels"]) for k in prompts}))
        cb.probe.freeze(out/"SETTLED.json",dict(rows=result,ledger=ledger))
if __name__=="__main__":main()
