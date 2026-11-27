"""Privately assemble the three fixed behavior probes; output contains no scores."""
from competition import (HERE, RUN, OUT, actor_request, author_module, author_wire, branch,
                         inputs, input_requests, read, select, sha, transfer)
from exposure_audit import receipts, stage_manifest
import argparse
import json

PREFIXES=("3776469a","7b03625e","ef273934")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cross-domain", action="store_true",
                        help="Inspect the sole exposed cross-domain source instead of the three fixed utility probes")
    parser.add_argument("--draw", type=int, choices=(1,2,3), default=1)
    args=parser.parse_args()
    if args.draw>1 and not args.cross_domain:
        parser.error("Utility cases have only one deployment")
    _,cases,tasks=inputs()
    prefixes=({uid.split("/")[-1][:8] for uid,c in cases.items() if c["category"]=="cross_domain"}
              if args.cross_domain else set(PREFIXES))
    assert len(prefixes)==(1 if args.cross_domain else 3)
    entries=assemble(args.draw,cases,tasks,prefixes)
    print(json.dumps(entries,ensure_ascii=False,indent=2))


def assemble(draw,cases,tasks,prefixes):
    draw_prefix=f"D{draw}"
    mod=author_module()
    protocol=read(HERE.parents[2]/"reports/qamc_persistbench_actor_factorial/PLAN.json")
    plan=read(transfer.OUT/"PLAN.json")
    banks={s:receipts(draw_prefix+s) for s in ("MA1","MA2","Route","Select","Actor")}
    manifest=stage_manifest(draw_prefix+"Actor")
    entries={}
    for uid,t in tasks.items():
        prefix=uid.split("/")[-1][:8]
        if prefix not in prefixes:
            continue
        entry=dict(query=t["query"],memories=t["memories"],arms={})
        entries[prefix]=entry
        wires={}
        ma=author_wire(mod,t,1)
        for i,stage in ((1,"MA1"),(2,"MA2")):
            status,answer=banks[stage].get(sha(ma),("missing",None))
            if status!="OK":
                entry["arms"]["MEMADAPTER"]=dict(status=stage+" "+status)
                break
            try:
                ma=author_wire(mod,t,i+1,answer)
            except (KeyError,TypeError,ValueError):
                entry["arms"]["MEMADAPTER"]=dict(status=stage+" invalid structure")
                break
        else:
            wires["MEMADAPTER"]=(ma,t["memories"])
        selectors=input_requests(cases[uid],t,plan)
        _,route=banks["Route"].get(sha(selectors["query"]),(None,None))
        if route:
            try:
                mode=branch(t,route)
                _,raw=banks["Select"].get(sha(selectors[mode]),(None,None))
                if raw:
                    selected=select(cases[uid],t,route,raw)
                    wide=t["memories"] if mode=="style" and selected else selected
                    for arm,ev in (("SELECTED",selected),("BREADTH",wide)):
                        wires[arm]=(actor_request(cases[uid],t["query"],ev,protocol,protocol["prompts"]["gepa"]),ev)
            except (KeyError,TypeError,ValueError):
                pass
        for arm,(wire,ev) in wires.items():
            key=sha(wire)
            assert manifest[key]==wire
            status,answer=banks["Actor"].get(key,("no returned receipt",None))
            entry["arms"][arm]=dict(status=status,actor_digest=key,evidence=ev,answer=answer)
        for arm in ("SELECTED","BREADTH"):
            entry["arms"].setdefault(arm,dict(status="selection unavailable"))
    assert set(entries)==prefixes
    return entries


if __name__=="__main__":
    main()
