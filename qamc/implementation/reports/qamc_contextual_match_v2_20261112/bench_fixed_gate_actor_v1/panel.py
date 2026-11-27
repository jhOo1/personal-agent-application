"""Freeze exposed repeat-study targets before generating with a new backbone."""
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RUN = BASE.parents[1] / "runs" / BASE.name / "benchpres_repeat_matched_v1"
GATE = "GEPA_SELECTED_BOUNDS"
def read(p):
    return json.loads(p.read_text())
def digest(v):
    return sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

def panel():
    plan=read(RUN/"PLAN_PRIVATE.json")
    cases={c["uid"]:c for c in plan["cases"]}
    assert all(not c["independent_confirmation"] for c in cases.values())
    gen={(j["unit"]["root_id"],j["unit"]["replicate"]):j["request"] for j in plan["generation"].values() if j["unit"]["method"]==GATE}
    scores={(r["uid"],r["replicate"]):r["score"] for p in sorted(RUN.glob("wave-*/RESULTS.json")) for r in read(p) if r["method"]==GATE and r.get("status")=="SCORED"}
    attrs=read(BASE/"strong_actor_boundary_audit_v1/CENSUS.json")["BenchPreS"]["attributes"]
    targets,controls=[],[]
    for a in attrs:
        uid=a["uid"]
        if a["expression"]!="SELECTED_EXACT" or "bold" in a["preference"].lower():
            continue
        draws=[scores.get((uid,i)) for i in range(3)]
        if not all(draws):
            continue
        ws=[gen[uid,i] for i in range(3)]
        if len({digest(w) for w in ws})!=1 or ws[0]["temperature"]!=1:
            raise ValueError("Unexpected wire drift")
        vals=[]
        for s in draws:
            hit=[x for x in s["decisions"] if x["preference"]==a["preference"] and x["appropriate"]]
            if len(hit)!=1:raise ValueError("Inconsistent preference identity")
            vals.append(hit[0]["label"]=="follow")
        row={"uid":uid,"profile":a["profile_group"],"position":a["position"],"repeat_follow":sum(vals),"request_sha256":digest(ws[0])}
        if a["base_follow"]!="follow" and sum(vals)<=1:targets.append(row)
        if a["base_follow"]=="follow" and all(vals) and all(s["mr_numerator"]==0 and s["task_completeness"]==5 for s in draws):controls.append(row)
    targets.sort(key=lambda r:(r["uid"],r["position"]))
    seen={r["uid"] for r in targets}; protected=[]
    by_profile=defaultdict(list)
    for r in sorted(controls,key=digest):by_profile[r["profile"]].append(r)
    while len(protected)<8 and any(by_profile.values()):
        for profile in sorted(by_profile):
            if not by_profile[profile]:continue
            r=by_profile[profile].pop()
            if r["uid"] not in seen:
                seen.add(r["uid"]);protected.append(r)
            if len(protected)==8:break
    return {"targets":targets,"controls":protected}
if __name__=="__main__":
    print(json.dumps(panel(),indent=2))
