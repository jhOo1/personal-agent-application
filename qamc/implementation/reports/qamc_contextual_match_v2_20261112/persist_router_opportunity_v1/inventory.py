"""Enumerate matching query-only receipts on the 60 exposed author-control tasks."""
from collections import Counter, defaultdict
from pathlib import Path
import json
from complete import input_requests, transfer
from trial import branch, sha, persist

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[2]/"runs"
BASE=RUN/HERE.parent.name

def read(path):
    return json.loads(path.read_text())

def main():
    roster=read(HERE.parent/"persist_author_controls_v2/PLAN.json")
    assert roster["not_confirmation"] and all(c["role"]=="DEV" for c in roster["cases"])
    old={r["uid"] for r in read(BASE/"persist_exposure_fr3_v1/RESULTS.json")["rows"]}
    route_plan=read(transfer.OUT/"PLAN.json")
    bank=defaultdict(list)
    dirs=[d for d in BASE.glob("*/*") if d.is_dir() and (d.name in ("Route","QueryRoute") or d.name.endswith("Route"))]
    for d in dirs:
        for f in d.glob("visible/*/record.json"):
            rec=read(f)
            bank[rec["request_sha256"]].append((f,rec))
    result=[]
    for c in roster["cases"]:
        t=persist.author.parent.smoke.task_for(c)
        public=dict(query=t.query,memories=[m.text for m in t.memories])
        assert sha(public)==c["public_sha256"]
        wire=input_requests(c,public,route_plan)["query"]
        seen=Counter()
        for f,rec in bank[sha(wire)]:
            assert read(f.parent/"request.json")==wire
            if rec["status"]!="OK":
                seen["failed"]+=1
                continue
            try: b=branch(public,read(f.parent/"response.json")["answer"])
            except (ValueError,KeyError,TypeError): b="invalid"
            seen[b]+=1
        result.append(dict(uid=c["uid"],track=c["category"],previous=c["uid"] in old,seen=seen))
    assert len(result)==60 and len(old)==49
    totals=defaultdict(Counter)
    for r in result:
        s=r["seen"]
        k=r["track"]+("/previous" if r["previous"] else "/outside")
        b="+".join(i for i in ("style","grounding") if s[i]) or "no_valid"
        totals[k][b]+=1
    return dict(roots=totals,scope="Exact query wire, visible receipt directories under contextual-match run root only",
                outside=[dict(prefix=r["uid"].split("/")[-1][:8],track=r["track"],observations=r["seen"]) for r in result if not r["previous"]])
if __name__=="__main__":print(json.dumps(main(),indent=2))
