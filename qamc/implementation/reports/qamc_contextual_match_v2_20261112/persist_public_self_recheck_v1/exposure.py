"""Compare visible original sources and recover actual answers by verified text hash."""
import json
import sys
from collections import Counter
from pathlib import Path
from qamc.common import sha

here=Path(__file__).resolve().parent
runs=here.parents[2]/"runs"/here.parent.name
out=runs/here.name
read=lambda p:json.loads(p.read_text())
old={(r["uid"],r["repeat"]):r for f in (runs/"persist_exposure_fr3_v1").glob("*_SETTLED.json") for r in read(f)["rows"]}
inputs={r["unit"]["root_id"]:json.loads(r["request"]["messages"][1]["content"]) for r in read(out/"private/D1Select_MANIFEST.json")["units"]}
probes=("0029f020","0613beea","3776469a","7b03625e","a47fceb8")
totals={}
for n in (1,2,3):
    drawn=out/f"DRAW_{n}.json"
    if not drawn.exists():continue
    physical={}
    for p in (out/f"D{n}Actor/visible").glob("*/record.json"):
        rec=read(p)
        if rec["status"]=="OK":
            answer=read(p.with_name("response.json"))["answer"]
            physical[sha(answer)]=answer
    for r in read(drawn)["rows"]:
        u=r["uid"]
        prior=old[u,n]
        memories=inputs[u]["retrieved_memories"]
        direct=None if "ids" not in r else [m["content"] for m in memories if m["memory_id"] in r["ids"]]
        exp=prior["exposure"] or {}
        selected=prior["methods"]["SELECTED"].get("actor") or {}
        t=totals.setdefault(r["track"],Counter())
        t["assigned"]+=1
        if direct is not None:
            t["empty"]+=not direct
            t["full"]+=len(direct)==len(memories)
        if direct is not None and exp.get("sha256"):
            t["both_selections"]+=1
            t["same_ordered_sources"]+=sha(direct)==exp["sha256"]
        if r.get("answer_hash"):
            answers={**physical,**{sha(a["answer"]):a["answer"] for cell in prior["methods"].values()
                                    if (a:=cell.get("actor")) and a.get("status")=="OK"}}
            ans=answers[r["answer_hash"]]
            assert sha(ans)==r["answer_hash"]
            if selected.get("status")=="OK":
                t["both_answers"]+=1
                t["identical_answers"]+=sha(selected["answer"])==sha(ans)
            if "--private" in sys.argv and u.split("/")[-1].startswith(probes):
                print(u,n,r.get("ids"),"DIRECT",ans,"SELECTED",selected.get("answer","UNKNOWN"))
print(json.dumps(totals,indent=2))
