"""Replay the frozen source-disjoint history-switch policies on archived endpoints."""
from collections import Counter, defaultdict
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent/"ipe_c_rate_matched_controls_v1"))
from audit_rate import FULL, ZERO, load, score

def grams(text):
    return set(zip(text, text[1:])) or set(text)

@lru_cache(None)
def similarity(a, b):
    x, y = grams(a), grams(b)
    return Fraction(len(x & y), len(x | y)) if x or y else Fraction(0)

def delta(r):
    return score(r,FULL,"Match")-score(r,ZERO,"Match")

def decide(value):
    return FULL if value>0 else ZERO

def prior(r, pool):
    exact = [s for s in pool if s["wire"]==r["wire"]]
    if exact:
        return decide(sum(map(delta,exact))), "exact"
    grouped = defaultdict(list)
    for s in pool:
        grouped[s["wire"]].append(s)
    strengths = {k:similarity(r["query"],rr[0]["query"]) for k,rr in grouped.items()}
    top = max(strengths.values(),default=0)
    if not top:
        return decide(sum(map(delta,pool))), "global"
    margin = sum(Fraction(sum(map(delta,grouped[k])),len(grouped[k])) for k,v in strengths.items() if v==top)
    return decide(margin), "neighbor"

def run():
    rows, pins = load()
    archive = json.loads((here.parent/"counterfactual_rpeval_v41/FROZEN.json").read_text())
    roots = {r["uid"]:r for r in archive["roots"]}
    labels = {r["uid"]:r["labels"] for r in json.loads((here.parent/"ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]}
    for r in rows:
        source = roots[r["uid"]]
        r["hist"]={sha256(x["text"].encode()).hexdigest() for x in source["original_sources"]}
        r["query"]=source["public_task"]["query"]
        assert r["hist"] and r["query"]
    modes=defaultdict(Counter); cards=defaultdict(lambda:defaultdict(Counter)); paired=defaultdict(Counter)
    train_sizes=[]
    for r in rows:
        pool=[s for s in rows if s["source_group"]!=r["source_group"] and s["hist"].isdisjoint(r["hist"])]
        assert pool and r not in pool
        train_sizes.append(len(pool))
        task,mode=prior(r,pool)
        modes["task"][mode]+=1
        conditional_pool=[s for s in pool if s["base"]==r["base"]]
        conditional, mode=prior(r,conditional_pool) if conditional_pool else (task,"fallback_task")
        modes["conditional"][mode]+=1
        loose,mode=prior(r,[s for s in rows if s["uid"]!=r["uid"]])
        modes["row_only"][mode]+=1
        arms={"empty":ZERO,"full":FULL,"IPE-C":r["base"],"global":decide(sum(map(delta,pool))),"task":task,"conditional":conditional,"row_only":loose}
        lab=labels[r["uid"]]
        strata=["all","contains C" if "C" in lab else "B without C" if "B" in lab else "all A"]
        if r["clean"]:strata.append("unflagged")
        for st in strata:
            for arm,m in arms.items():
                c=cards[st][arm]
                c.update(tasks=1,positions=r["positions"],open=int(m==FULL))
                for f in ("Match","OPB","UPB","FM"):
                    if all(score(r,k,f) is not None for k in (ZERO,FULL)):
                        c[f]+=score(r,m,f);c[f+"_n"]+=1
        for x,y in (("conditional","task"),("conditional","IPE-C"),("IPE-C","task")):
            diff=score(r,arms[x],"Match")-score(r,arms[y],"Match")
            paired[x+" vs "+y]["win" if diff>0 else "loss" if diff<0 else "tie"]+=1
    return dict(source_file_hashes=pins,train_size_range=[min(train_sizes),max(train_sizes)],modes=modes,cards=cards,paired=paired)

if __name__=="__main__":
    print(json.dumps(run(),indent=2))
