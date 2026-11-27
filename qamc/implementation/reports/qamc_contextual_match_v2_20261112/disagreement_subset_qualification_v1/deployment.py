"""Replay three pre-specified policies with the original IPE-C answer outside the trigger."""
from collections import Counter, defaultdict
import json
from run_off import HERE, previous_run, read
from read_side import probe
from qamc.common import parse_object

archive=read(HERE.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
raw=read(previous_run.with_name(HERE.name)/"RESULTS.json")
frozen=read(HERE/"ACTOR_HASHES.json")
fresh={}
lengths={r["uid"]:len(r["labels"] or "") for r in archive}
for r in raw["rows"]:
    uid,arm=r["uid"],r["arm"]
    assert r["actor"]["status"]==r["judge"]["status"]=="OK"
    grade,_=probe.fields(parse_object(r["judge"]["answer"]),lengths[uid],True)
    assert (uid,arm) not in fresh and grade.get("match")
    fresh[uid,arm]=grade
assert {u+"/"+a for u,a in fresh}==set(frozen)
counts=defaultdict(Counter)
source_delta=defaultdict(Counter)
triggered=set()
for r in archive:
    if not all(v["grade"].get("match") for v in r["scores"].values()):
        continue
    uid=r["uid"]
    orig=r["scores"]["IPE_C"]
    g=orig["grade"]
    changed=(uid,"DISAGREE") in fresh
    if changed:
        assert orig==r["scores"]["TASK_ONLY"]
        triggered.add(uid)
    for arm in ("IPE_C","DISAGREE","RP_K"):
        s=fresh.get((uid,arm),g)
        tally=counts[arm]
        tally.update(tasks=1,positions=s["match"]["positions"],match=s["match"]["matched"])
        for field in ("full_match","OPB","UPB","FM"):
            if field in s:
                tally[field]+=s[field]
                tally[field+"_valid"]+=1
        source_delta[arm][r["source_group"]]+=s["match"]["matched"]-g["match"]["matched"]
assert len(triggered)==24 and len(fresh)==48
print(json.dumps({"assigned":len(archive),"triggered":len(triggered),"overall":counts,
    "net_match_by_root_vs_original":{a:Counter("win" if v>0 else "loss" if v<0 else "tie"
                                     for v in ds.values()) for a,ds in source_delta.items()}},indent=2,sort_keys=True))
