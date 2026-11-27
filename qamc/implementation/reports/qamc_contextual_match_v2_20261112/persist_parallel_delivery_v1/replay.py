"""Branch on Actor delivery only; then join fixed-answer grades."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import sys

BASE=Path(__file__).resolve().parents[1]
RUN=BASE.parents[1]/"runs"/BASE.name
sys.path.insert(0,str(BASE/"persist_selected_crossjudge_fr3_v1"))
from settle import outcome

def read(p):return json.loads(p.read_text())

def route(primary, alternate, arrived):
    if arrived[primary]:return primary
    if arrived[alternate]:return alternate
    return None

def main():
    alloc={}
    counts=defaultdict(Counter)
    for f in sorted((RUN/"persist_exposure_fr3_v1").glob("*_SETTLED.json")):
        for r in read(f)["rows"]:
            arrived={}
            for name in ("SELECTED","RUBRIC"):
                a=r["methods"][name].get("actor") or {}
                arrived[name]=a.get("status")=="OK" and bool(a.get("answer"))
            k=(r["uid"],r["repeat"])
            assert k not in alloc
            paths={"S": "SELECTED" if arrived["SELECTED"] else None,
                   "R": "RUBRIC" if arrived["RUBRIC"] else None,
                   "S_first":route("SELECTED","RUBRIC",arrived),"R_first":route("RUBRIC","SELECTED",arrived)}
            alloc[k]=(r["track"],paths)
            counts[r["track"]].update(positions=1,both=int(all(arrived.values())),
                S_only=int(arrived["SELECTED"] and not arrived["RUBRIC"]),
                R_only=int(arrived["RUBRIC"] and not arrived["SELECTED"]),neither=int(not any(arrived.values())))
    grades={(r["uid"],r["repeat"],r["arm"]):r for r in read(RUN/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"]}
    assert len(alloc)==111 and len(grades)==222
    roots=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    for (u,i),(track,paths) in sorted(alloc.items()):
        for n,origin in paths.items():
            roots[track][u][n].append(grades[u,i,origin] if origin else {"old":None,"qwen":None})
    totals=defaultdict(lambda:defaultdict(Counter))
    pairs=defaultdict(lambda:defaultdict(Counter))
    for track,us in roots.items():
        for u,arms in us.items():
            for j in ("old","qwen"):
                values={n:outcome(draws,track,j) for n,draws in arms.items()}
                for n,v in values.items():totals[track][j+"/"+n]["unknown" if v is None else "fail" if v else "pass"]+=1
                left,right=values["S_first"],values["R_first"]
                result="unknown" if None in (left,right) else "win" if right and not left else "loss" if left and not right else "tie"
                pairs[track][j][result]+=1
    return {"delivery":counts,"root_outcomes":totals,"symmetric_priority_pairs":pairs}
if __name__=="__main__":print(json.dumps(main(),indent=2))
