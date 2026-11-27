"""Attribute missing external answers to the first observed stage, never to semantics."""
import json
from collections import Counter
from competition import BU, OUT, RUN, author_module, author_wire, inputs, read, sha


def track(draw,cases,tasks,mod):
    stages=("MA1","MA2","Actor")
    stored={}
    manifests={}
    for name in stages:
        key=f"D{draw}{name}"
        records={}
        for path in (RUN/key/"visible").glob("*/record.json"):
            rec=read(path)
            digest=rec["request_sha256"]
            assert digest not in records
            records[digest]=(rec,path)
        stored[name]=records
        manifest=OUT/f"{key}_MANIFEST.json"
        manifests[name]={e["unit"]["root_id"] for e in read(manifest)["units"]} if manifest.exists() else None
    groups={}
    for uid,case in cases.items():
        if draw>1 and case["category"]==BU:
            continue
        task=tasks[uid]
        wire=author_wire(mod,task,1)
        for n,name in enumerate(stages,1):
            digest=sha(wire)
            if manifests[name] is None:
                label="awaiting_"+name
                break
            if digest not in manifests[name]:
                raise ValueError(f"Registered {name} stage lacks an expected wire")
            if digest not in stored[name]:
                label=name+"_unsettled"
                break
            rec,path=stored[name][digest]
            if rec["status"]!="OK":
                label=name+"_"+rec["status"]
                break
            assert sha(read(path.with_name("request.json")))==digest
            if n==3:
                label="delivered"
                break
            answer=read(path.with_name("response.json"))["answer"]
            try:
                wire=author_wire(mod,task,n+1,answer)
            except (TypeError,ValueError,KeyError):
                label=name+"_invalid_structure"
                break
        groups.setdefault(case["category"],Counter())[label]+=1
    return groups


if __name__=="__main__":
    _,cases,tasks=inputs()
    mod=author_module()
    print(json.dumps({d:track(d,cases,tasks,mod) for d in range(1,4)
                      if (OUT/f"D{d}MA1_MANIFEST.json").exists()},indent=2))
