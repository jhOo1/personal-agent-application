"""Report fresh-arm comparisons and exact reused strong reference grades."""
from collections import Counter,defaultdict
import json
from trial import OUT,BASE,read,prepare
from qamc_rpeval_terminal_judge_sensitivity import inspect

def report():
    data=read(OUT/"RESULTS.json")
    wires=prepare()
    ids=sorted({u for u,a in wires})
    prior={r["uid"]:r for r in read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    old={r["uid"]:r for r in read(BASE/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json") if r["method"]=="DES2GEN_FULL"}
    cells={(e["uid"],e["arm"]):e["score"] for e in data["rows"]}
    totals=defaultdict(lambda:defaultdict(Counter))
    diffs=defaultdict(Counter)
    hidden=Counter()
    case_diffs=[]
    for uid in ids:
        base=prior[uid]
        original=old[uid]
        scores={arm:cells.get((uid,arm),{}) for arm in ("full","masked")}
        scores["IPE-C"]=base["ipe_c"]
        g=original.get("native_fields") or {}
        scores["historical_full"]={"grade":g,"flags":inspect(original,base["labels"])["flags"] if g.get("match") else None}
        dec=json.loads(wires[uid,"full"]["messages"][-1]["content"])["applicability_decisions"]
        assert len(dec)==len(base["labels"])
        for d,label in zip(dec,base["labels"]):
            if d["decision"]=="Suppress":hidden[label]+=1
        for subset,names in (("fresh",("masked","full")),("strong",("masked","full","IPE-C")),("all",tuple(scores))):
            if any(not scores[n].get("grade",{}).get("match") or any(scores[n]["grade"].get(m) is None for m in ("OPB","UPB","FM")) for n in names):continue
            for scope in ["raw"]+(["unflagged"] if all(scores[n]["flags"]==[] for n in names) else []):
                k=subset+"/"+scope
                for n in names:
                    f=scores[n]["grade"];m=f["match"]
                    assert m["positions"]==len(base["labels"])
                    totals[k][n].update(tasks=1,Match=m["matched"],positions=m["positions"],**{i:f[i] for i in ("OPB","UPB","FM")})
                value=lambda n:scores[n]["grade"]["match"]["matched"]
                diffs[k]["beat_all"]+=int(all(value("masked")>value(n) for n in names[1:]))
                if subset=="strong" and scope=="raw":case_diffs.append([uid,value("masked"),value("full"),value("IPE-C")])
    ledger=data["ledger"]
    return dict(assigned=len(ids),hidden_author_positions=hidden,tables=totals,paired=diffs,
                statuses=Counter(r["status"] for r in ledger),tokens=sum((r["usage"] or {}).get("total_tokens",0) for r in ledger),
                unknown_usage=sum((r["usage"] or {}).get("total_tokens") is None for r in ledger),development_cases=case_diffs)
if __name__=="__main__":print(json.dumps(report(),indent=2))
