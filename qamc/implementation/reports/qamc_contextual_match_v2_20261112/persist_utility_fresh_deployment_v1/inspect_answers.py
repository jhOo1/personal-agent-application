"""Reconstruct exact per-arm responses for a private case read without dispatch."""
import argparse
import json
from pathlib import Path
from trial import OUT,prepare,sha,select,actor_request,branch

def records(stage):
    base=OUT.parent/stage/"visible"
    table={}
    for p in base.glob("*/record.json"):
        r=json.loads(p.read_text());w=json.loads((p.parent/"request.json").read_text())
        assert sha(w)==r["request_sha256"]
        if r["status"]=="OK":
            table[sha(w)]=json.loads((p.parent/"response.json").read_text())["answer"]
    return table

def read_case(prefix):
    cases,items,proto,_,_=prepare()
    matches=[u for u in cases if cases[u]["category"]=="beneficial_memory_usage" and u.split("/")[-1].startswith(prefix)]
    if len(matches)!=1:raise ValueError("Expected exactly one exposed utility task")
    uid=matches[0];item=items[uid];q=item["public"];sel=item["selection_requests"]
    route=records("Route").get(sha(sel["query"]));sources=None
    if route:
        try:
            decision=records("Select").get(sha(sel[branch(q,route)]))
            if decision:sources=select(cases[uid],q,route,decision)
        except (KeyError,ValueError,TypeError):pass
    wires={a:item[a] for a in ("FULL","RUBRIC")}
    if sources is not None:wires["SELECTED"]=actor_request(cases[uid],q["query"],sources,proto,proto["prompts"]["gepa"])
    bank=records("Actor")
    return {"uid":uid,"public":q,"selected_sources":sources,
            "arms":{k:{"wire":sha(v),"answer":bank.get(sha(v))} for k,v in wires.items()}}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("uid_prefix")
    print(json.dumps(read_case(p.parse_args().uid_prefix),indent=2))
