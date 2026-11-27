"""Pair frozen induction responses with their exact development comparators."""
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RUN=HERE.parents[2]/"runs"/BASE.name/HERE.name
ARMS=("induction","ordinary","IPE-C","RP","Gate")
def read(p):return json.loads(p.read_text())
def comparison(rows,names,clean=False):
    counts={a:Counter() for a in names}
    wins=Counter()
    groups=set()
    for r in rows:
        if not all(a in r["scores"] for a in names):continue
        scores={a:r["scores"][a] for a in names}
        if clean and any(v["flags"] is None or v["flags"] for v in scores.values()):continue
        for a,v in scores.items():counts[a].update(v["metrics"])
        diff=scores[names[0]]["metrics"]["Match"]-scores[names[1]]["metrics"]["Match"]
        wins["win" if diff>0 else "loss" if diff<0 else "tie"]+=1
        if diff>0:groups.add(r["group"])
    return {"matched":sum(wins.values()),"arms":counts,"paired":wins,"winning_groups":len(groups)}

def report():
    frozen=read(RUN/"private/FROZEN.json")["roster"]
    result=read(RUN/"private/RESULTS.json")
    frontier={r["uid"]:r for r in read(BASE/"selective_path_frontier_v1/RESULTS.json")["rows"]}
    cells={(r["uid"],r["arm"]):r["score"] for r in result["rows"]}
    assert len(cells)==len(result["rows"])
    rows=[]
    for u,stratum in frozen.items():
        row=frontier[u];scores={}
        for a in ARMS:
            if a in ("ordinary","induction"):
                s=cells.get((u,a)) or {};g=s.get("grade",{});match=g.get("match") or {}
                matched=match.get("matched");flags=s.get("flags")
                if matched is not None:assert match["positions"]==row["positions"]
            else:
                key={"IPE-C":row["base"],"RP":"RPR_PAPER_FULL","Gate":"GEPA_SELECTED_BOUNDS"}[a]
                c=row["cells"].get(key) or {};g=c.get("fields",{});matched=c.get("matched");flags=c.get("flags")
            if matched is None or any(g.get(k) is None for k in ("OPB","UPB","FM")):continue
            scores[a]={"flags":flags,"metrics":{"positions":row["positions"],"Match":matched,**{k:g[k] for k in ("OPB","UPB","FM")}}}
        rows.append({"group":row["source_group"],"stratum":stratum,"scores":scores})
    tables={}
    for s in ("all","B_only","contains_C","all_A"):
        subset=[r for r in rows if s=="all" or r["stratum"]==s]
        tables[s]={"assigned":len(subset),"five_way":comparison(subset,ARMS),
                   "all_five_unflagged":comparison(subset,ARMS,True),
                   "pairwise":{a:comparison(subset,("induction",a)) for a in ARMS[1:]}}
    return {"tables":tables,"status":Counter(x["status"] for x in result["ledger"]),
            "reported_tokens":sum((x["usage"] or {}).get("total_tokens",0) for x in result["ledger"]),
            "unknown_usage":sum((x["usage"] or {}).get("total_tokens") is None for x in result["ledger"])}
if __name__=="__main__":print(json.dumps(report(),indent=2))
