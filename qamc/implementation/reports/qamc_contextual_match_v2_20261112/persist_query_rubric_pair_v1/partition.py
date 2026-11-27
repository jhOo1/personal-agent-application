"""Single-draw transfer comparison; require exact comparator scorer wire."""
from collections import Counter,defaultdict
from compare import HERE,RUN,read
from trial import prepare,judge_wire,sha
cases,items,_,settings,bounds=prepare()
grade=judge_wire(cases,items,settings,bounds)
controls=read(HERE.parent/"persist_structured_competitor_v1/QWEN_RESULTS.json")["rows"]
receipts={}
for p in (RUN/"persist_structured_qwen_v1/PersistJudge/visible").glob("*/record.json"):
    rec=read(p)
    if rec["status"]=="OK":
        wire=read(p.parent/"request.json")
        assert rec["request_sha256"]==sha(wire)
        receipts[sha(wire)]=wire
old=read(RUN/"persist_exposure_fr3_v1/RESULTS.json")["rows"]
candidate={r["uid"]:(r["methods"]["SELECTED"]["score"] or {}).get("rating") for r in old if r["track"]!="beneficial_memory_usage" and r["repeat"]==1}
opened=set(read(HERE.parent/"persist_query_requested_open_v1/SUMMARY.json")["utility_changed"])
for r in read(RUN/"persist_utility_fresh_deployment_v1/private/SETTLED.json")["rows"]:
    arm="FULL" if r["uid"].split("/")[-1][:8] in opened else "SELECTED"
    if r["arm"]==arm:candidate[r["uid"]]=r["GPT"]
out=defaultdict(Counter)
for r in controls:
    if r["method"]!="PARTITION":continue
    uid=r["uid"]
    if uid not in candidate:
        out["coverage"]["outside"]+=1;continue
    track=cases[uid]["category"]
    out[track]["assigned"]+=1
    if r["score"] is None or candidate[uid] is None:
        out[track]["unknown"]+=1;continue
    wire=grade(uid,r["answer"])
    if sha(wire) not in receipts:
        out[track]["unmatched_wire"]+=1;continue
    def ok(n):return n==3 if track=="beneficial_memory_usage" else n<3
    a,b=ok(candidate[uid]),ok(r["score"]["rating"])
    out[track]["query_pass"]+=int(a);out[track]["partition_pass"]+=int(b)
    out[track]["win" if a>b else "loss" if a<b else "tie"]+=1
import json
print(json.dumps(out,indent=2))
