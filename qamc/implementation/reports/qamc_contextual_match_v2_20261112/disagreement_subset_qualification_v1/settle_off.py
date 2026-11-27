"""Aggregate frozen paired outcomes; keep failures out of semantic scores."""
import json
from collections import Counter, defaultdict
from run_off import HERE, previous_run, read
from read_side import probe
from qamc.common import parse_object

def settle():
    raw=read(previous_run.with_name(HERE.name)/"RESULTS.json")
    endpoints={r["uid"]:r for r in read(HERE.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    hashes=read(HERE/"ACTOR_HASHES.json")
    by_uid=defaultdict(dict)
    status=Counter()
    for r in raw["rows"]:
        uid,arm=r["uid"],r["arm"]
        judge=r["judge"]
        if not judge or judge["status"]!="OK":
            status[(judge or r["actor"])["status"]]+=1
            continue
        try:
            g,_=probe.fields(parse_object(judge["answer"]),len(endpoints[uid]["labels"]),True)
        except (ValueError,KeyError,TypeError):
            g={}
        if not all(k in g for k in ("match","full_match","OPB","UPB","FM")):
            status["INVALID_GRADE"]+=1
            continue
        by_uid[uid][arm]=g
        status["VALID"]+=1
    totals=defaultdict(lambda:defaultdict(Counter))
    grouped=Counter()
    for uid,arms in by_uid.items():
        if len(arms)!=2:continue
        different=hashes[uid+"/DISAGREE"]!=hashes[uid+"/RP_K"]
        arms.update({m:endpoints[uid]["scores"][m]["grade"] for m in ("TASK_ONLY","RPR_PAPER_FULL")})
        labels=endpoints[uid]["labels"]
        stratum="contains_C" if "C" in labels else "contains_B_no_C" if "B" in labels else "all_A"
        for bucket in ["paired",stratum]+(["different_input"] if different else []):
            for method,g in arms.items():
                a=totals[bucket][method]
                a.update(tasks=1,positions=len(labels),match=g["match"]["matched"],exact=g["full_match"])
                for field in ("OPB","UPB","FM"):
                    if field in g:
                        a[field]+=g[field]
                        a[field+"_tasks"]+=1
        grouped[endpoints[uid]["source_group"]]+=arms["DISAGREE"]["match"]["matched"]-arms["RP_K"]["match"]["matched"]
    ledger=raw["ledger"]
    return dict(allocated=24,status=status, paired=totals,root_net=Counter("win" if d>0 else "loss" if d<0 else "tie" for d in grouped.values()),
                calls=len(ledger),calls_by_status=Counter(r["status"] for r in ledger),
                tokens=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger),
                unknown_usage=sum("total_tokens" not in (r.get("usage") or {}) for r in ledger))
if __name__=="__main__": print(json.dumps(settle(),indent=2,sort_keys=True))
