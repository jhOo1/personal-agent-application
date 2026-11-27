"""Trace both switches to actual receipts and report paired metric coverage."""
from collections import Counter, defaultdict
import json
import sys
from pathlib import Path
here=Path(__file__).resolve().parent
sys.path.insert(0,str(here.parent/"ipe_c_rate_matched_controls_v1"))
from audit_rate import load, FULL, ZERO, score
from qamc.common import sha
def read(p):
    return json.loads(p.read_text())
run=here.parents[2]/"runs"/here.parent.name/(here.name+"_usage")
pin=read(run/"private/FROZEN.json")
by_task={r["uid"]:r for r in load()[0]}
roots={r["uid"]:r for r in read(here.parent/"counterfactual_rpeval_v41/FROZEN.json")["roots"]}
dec={}
for p in (run/"HistorySwitch/visible").glob("*/record.json"):
    receipt=read(p)
    wire=read(p.with_name("request.json"))
    assert sha(wire)==receipt["request_sha256"]
    if receipt["status"]=="OK":
        dec[sha(json.loads(wire["messages"][1]["content"]))]={"ON":FULL,"OFF":ZERO}.get(read(p.with_name("response.json"))["answer"].strip())
totals=Counter()
groups=defaultdict(list)
denoms=Counter()
for uid in pin["panel"]:
    r=by_task[uid]
    root=roots[uid]
    q=dec.get(sha(root["public_task"]))
    h=dec.get(sha(dict(root["public_task"],history=root["original_sources"])))
    if None in (q,h):
        continue
    for metric in ("Match","OPB","UPB","FM"):
        denoms[metric]+=all(score(r,arm,metric) is not None for arm in (FULL,ZERO))
    delta=score(r,h,"Match")-score(r,q,"Match")
    totals["win" if delta>0 else "loss" if delta<0 else "tie"]+=1
    groups[r["wire"]].append((q,h,delta))
print("\n## Paired outcomes\n")
print("History-aware versus query-only by task (Match):",dict(totals))
gcounts=Counter(); split=0
for items in groups.values():
    if len(items)!=2:
        continue
    assert len({x[0] for x in items})==1
    split+=len({x[1] for x in items})==2
    delta=sum(x[2] for x in items)
    gcounts["win" if delta>0 else "loss" if delta<0 else "tie"]+=1
print("\nComplete matched task groups:",sum(gcounts.values()),"; different history-aware decisions across their two histories:",split,"; group wins/losses/ties:",dict(gcounts))
print("\nPaired task denominators for severity sums and Match:",dict(denoms))
print("\n### Within-request discrimination (exploratory)\n")
observed=expected=0
for uid in pin["panel"]:
    r=by_task[uid]
    root=roots[uid]
    items=groups[r["wire"]]
    if len(items)!=2:
        continue
    h=dec[sha(dict(root["public_task"],history=root["original_sources"]))]
    observed+=score(r,h,"Match")
    rate=sum(x[1]==FULL for x in items)/len(items)
    expected+=(1-rate)*score(r,ZERO,"Match")+rate*score(r,FULL,"Match")
print(f"On complete groups, observed history-aware Match {observed}; expected Match {expected:.1f} when its opening count stays fixed within each identical request and assignments of openings to histories are uniform. This diagnostic conditions on observed decisions and uses archived scores.")
