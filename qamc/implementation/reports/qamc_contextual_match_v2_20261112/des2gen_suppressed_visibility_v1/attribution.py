"""Post hoc observability of overuse with exactly the delivered memory texts."""
import json
from collections import Counter,defaultdict
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
RUN=BASE.parents[1]/"runs"/BASE.name/"des2gen_suppressed_visibility_v1"

def read(p):
    return json.loads(p.read_text())

def report():
    labels={r["uid"]:r["labels"] for r in read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    rows=read(RUN/"private/RESULTS.json")["rows"]
    scores={(r["uid"],r["arm"]):r["score"] for r in rows}
    totals=defaultdict(lambda:defaultdict(Counter))
    for p in (RUN/"Actor/visible").glob("*/record.json"):
        unit=read(p)["unit"]
        if unit["method"]!="masked":continue
        uid=unit["root_id"]
        w=json.loads(read(p.parent/"request.json")["messages"][-1]["content"])
        src=w["source_evidence"]
        assert len(src)==len(labels[uid])
        visible=[v for v,s in zip(labels[uid],src) if s["text"]]
        k="visible_A" if "A" in visible else "no_visible_A"
        b="author_B" if "B" in labels[uid] else "no_author_B"
        for category in (k,k+"/"+b):
            for arm in ("full","masked"):
                s=scores[uid,arm];g=s["grade"]
                assert g.get("OPB") is not None
                t=totals[category][arm]
                t.update(tasks=1,opb=g["OPB"],positive=int(g["OPB"]>0),match_available=int(bool(g.get("match"))))
                if g.get("match") and s["flags"]==[]:
                    t.update(clean_tasks=1,clean_opb=g["OPB"],clean_positive=int(g["OPB"]>0))
    return totals
if __name__=="__main__":print(json.dumps(report(),indent=2))
