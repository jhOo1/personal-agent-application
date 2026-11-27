"""Reconcile the soft-only stratum, and bound archived third-answer opportunities."""
import json
from collections import defaultdict, Counter
from pathlib import Path

here=Path(__file__).resolve().parent
base=here.parent
def read(path):
    return json.loads(path.read_text())
routes=read(base/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
external=defaultdict(dict)
methods=("MEMADAPTER_FULL","DES2GEN_FULL","GEPA_SELECTED_BOUNDS")
for r in read(base/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json"):
    if r["method"] in methods:
        external[r["uid"]][r["method"]]=r["native_fields"] or {}
def soft(r):
    labels=r["labels"] or ""
    return "B" in labels and "C" not in labels
print("# B present, C absent: archived generation opportunities\n")
print("The project's soft-only task stratum allows A distractors. A task containing exclusively B labels is a different, narrower condition.")
eligible=[r for r in routes if soft(r)]
print(f"\nFrozen archive: {len(routes)} tasks; {len(eligible)} have a B and no C.")
sets=Counter();groups=set();opportunities=[]
for r in eligible:
    endpoints=[r["scores"][m]["grade"] or {} for m in ("TASK_ONLY","RPR_PAPER_FULL")]
    if not all(g.get("match") for g in endpoints):continue
    n=len(r["labels"])
    assert all(g["match"]["positions"]==n for g in endpoints)
    sets["both_valid"]+=1
    if not all(g["match"]["matched"]<n and (g.get("UPB") or 0)>0 for g in endpoints):continue
    sets["both_imperfect_positive_UPB"]+=1
    for m in methods:
        g=external[r["uid"]].get(m,{})
        if not g.get("match"):continue
        assert g["match"]["positions"]==n
        sets[m+"_valid"]+=1
        if g["match"]["matched"]<=max(e["match"]["matched"] for e in endpoints):continue
        sets[m+"_higher"]+=1
        if not all(type(z.get(k))==int for z in (g,*endpoints) for k in ("OPB","UPB","FM")):continue
        if all(g[k]<=min(e[k] for e in endpoints) for k in ("OPB","UPB","FM")):
            sets[m+"_protected"]+=1;groups.add(r["source_group"])
            opportunities.append((r["uid"],m,g["match"]["matched"],n))
print("\nCounts:",dict(sets))
print(f"\nUnique tasks with higher Match than both endpoints and no larger OPB, UPB or FM than either: {len(set(x[0] for x in opportunities))}; source groups: {len(groups)}. Results are an archive screen. Positive severity is a grader signal; it does not locate an individual omitted memory or prove a behavioral improvement.")
roots={r["uid"]:r for r in routes}
run=here.parents[2]/"runs"/base.name/"rpe_deployable_history_gate_v1_usage/private"
panel=read(run/"FROZEN.json")["panel"]
cases=[roots[u] for u in panel if soft(roots[u])]
print("\n## Correction to the previous 24-task switch report\n")
print(f"{len(cases)}/24 cases, {sum(len(r['labels']) for r in cases)} positions belong to the established soft-only stratum. The historical literal all-B filter returned zero. Overall results stand.")
import hashlib
def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
archive=read(base/"counterfactual_rpeval_v41/FROZEN.json")["roots"]
tasks={r["uid"]:r for r in archive}
observed={}
for path in run.parent.glob("HistorySwitch/visible/*/record.json"):
    receipt=read(path)
    wire=read(path.with_name("request.json"))
    assert digest(wire)==receipt["request_sha256"] and receipt["status"]=="OK"
    packet=json.loads(wire["messages"][1]["content"])
    answer=read(path.with_name("response.json"))["answer"].strip()
    assert answer in ("ON","OFF")
    observed[digest(packet)]=answer
print("\n|Arm|Match / positions|OPB|UPB|FM|\n|---|---:|---:|---:|---:|")
for arm in ("query","memory","IPE_C","TASK_ONLY","RPR_PAPER_FULL"):
    scores=Counter()
    for r in cases:
        t=tasks[r["uid"]]
        key=arm
        if arm in ("query","memory"):
            packet=dict(t["public_task"])
            if arm=="memory":packet["history"]=t["original_sources"]
            key="RPR_PAPER_FULL" if observed[digest(packet)]=="ON" else "TASK_ONLY"
        g=r["scores"][key]["grade"]
        scores.update({k:g[k] for k in ("OPB","UPB","FM")})
        scores.update(g["match"])
    print(f"|{arm}|{scores['matched']}/{scores['positions']}|{scores['OPB']}|{scores['UPB']}|{scores['FM']}|")
if __name__=="__main__":
    import sys
    if "--private" in sys.argv:print(opportunities)
