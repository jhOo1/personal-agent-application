"""Compare with saved same-item strong methods under the matched score adapters."""
from collections import Counter
import json

from baselines import archive, HERE
from summarize_reassembly import measure


def external():
    plan=archive.read(HERE/"FROZEN.json")
    outcome=archive.read(HERE/"RESULTS.json")
    refs={r["uid"]:r for r in plan["rows"]}
    candidates={(r["uid"],r["method"]):r for r in outcome["rows"]}
    rpe_names=(archive.engine.GATE,archive.engine.RP,"MEMADAPTER_FULL","DES2GEN_FULL")
    rpe=[r for r in archive.read(archive.v41.formal.OUT/"RESULT_ROWS.json")
         if r["uid"] in refs and r["method"] in rpe_names and r["actor_status"]=="OK" and
         r.get("raw_scores",{}).get(archive.v41.NATIVE)]
    metrics={(r["uid"],r["method"]):r["native_fields"] for r in rpe}
    controls={}
    for b,names in (
            ("BenchPreS",(archive.engine.GATE,archive.engine.RP,"PAPER_SELECTIVITY","MEMADAPTER_FULL","DES2GEN_FULL")),
            ("PersistBench",(archive.engine.GATE,archive.engine.RP,"PB_RUBRIC","PB_GEPA","PB_NO_MEMORY"))):
        cases,_,rows=archive.transfer.context(b)
        controls[b]=names
        for r in rows:
            if r["uid"] in refs and r["uid"] in cases and r["method"] in names and r["score"] is not None:
                k=(r["uid"],r["method"])
                if k in metrics and metrics[k]!=r["score"]:
                    raise ValueError("Inconsistent external comparator")
                metrics[k]=r["score"]
    controls["RPEval"]=rpe_names
    groups={}
    for b,names in controls.items():
        group={}
        for method in names:
            for arm in ("FREE","TATR"):
                lhs,rhs,by_kind=Counter(),Counter(),{}
                n=0
                for uid, c in refs.items():
                    old=metrics.get((uid,method))
                    if c["benchmark"]!=b or old is None:
                        continue
                    a,z=(measure(b,c["stratum"],s) for s in (old,candidates[uid,arm]["score"]))
                    if a is None or z is None:
                        continue
                    if a["positions"]!=z["positions"]:
                        raise ValueError("Comparator position mismatch")
                    lhs.update(a)
                    rhs.update(z)
                    p=by_kind.setdefault(c["stratum"],Counter())
                    p.update(tasks=1,positions=a["positions"],reference=a["primary"],revised=z["primary"])
                    n+=1
                group[method+"/"+arm]={"n":n,"reference":lhs,"revised":rhs,"strata":by_kind}
        groups[b]=group
    return {"results":groups,"new_requests":0,"matched_scoring":True,
            "generation_compute_matched":False,"development_only":True}


if __name__=="__main__":
    print(json.dumps(external(),ensure_ascii=False,indent=2))
