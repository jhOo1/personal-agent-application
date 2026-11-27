"""Verify logical arms against physically dispatched Actor messages without scoring them."""
from collections import Counter
import json
from pathlib import Path
from competition import (BU, HERE, RUN, OUT, actor_request, branch, inputs,
                         input_requests, read, select, sha, transfer)


def stage_manifest(stage):
    entries = read(OUT/f"{stage}_MANIFEST.json")["units"]
    result = {}
    for entry in entries:
        digest = sha(entry["request"])
        assert digest == entry["unit"]["root_id"] and digest not in result
        result[digest] = entry["request"]
    return result


def receipts(stage):
    result = {}
    for path in (RUN/stage/"visible").glob("*/record.json"):
        r = read(path)
        key = r["request_sha256"]
        assert key not in result and sha(read(path.with_name("request.json"))) == key
        result[key] = (r["status"], read(path.with_name("response.json"))["answer"] if r["status"]=="OK" else None)
    return result


def replay(draw,cases,tasks,plan,protocol):
    prefix = f"D{draw}"
    actor = stage_manifest(prefix+"Actor")
    routes = receipts(prefix+"Route")
    selectors = receipts(prefix+"Select")
    counts = {}
    accounted = set()
    for uid,task in tasks.items():
        case = cases[uid]
        if draw>1 and case["category"]==BU:
            continue
        c = counts.setdefault(case["category"],Counter())
        c["assigned"] += 1
        wires = input_requests(case,task,plan)
        rs,route = routes.get(sha(wires["query"]),("missing",None))
        if rs!="OK":
            c["route_unavailable"]+=1
            continue
        try:
            mode=branch(task,route)
        except (KeyError,TypeError,ValueError):
            c["invalid_route"]+=1
            continue
        ss,selection=selectors.get(sha(wires[mode]),("missing",None))
        if ss!="OK":
            c["selector_unavailable"]+=1
            continue
        try:
            original=select(case,task,route,selection)
        except (KeyError,TypeError,ValueError):
            c["invalid_selector"]+=1
            continue
        widened=task["memories"] if mode=="style" and original else original
        keys=[]
        for evidence in (original,widened):
            wire=actor_request(case,task["query"],evidence,protocol,protocol["prompts"]["gepa"])
            digest=sha(wire)
            if actor.get(digest)!=wire:
                raise ValueError("Replayed Actor request differs from physical manifest")
            keys.append(digest)
            accounted.add(digest)
        c["changed" if keys[0]!=keys[1] else "identical"]+=1
        c["empty_selection"]+=int(not original)
    return dict(tracks=counts,unique_internal_actor_requests=len(accounted),unique_all_actor_requests=len(actor))


def main():
    _,cases,tasks=inputs()
    plan=read(transfer.OUT/"PLAN.json")
    protocol=read(HERE.parents[2]/"reports/qamc_persistbench_actor_factorial/PLAN.json")
    report={}
    for draw in range(1,4):
        if (OUT/f"D{draw}Actor_MANIFEST.json").exists():
            report[draw]=replay(draw,cases,tasks,plan,protocol)
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
