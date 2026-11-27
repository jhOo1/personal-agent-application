"""Optimistic bound on four incomplete but potentially useful BenchPreS answers."""
from collections import Counter, defaultdict
import json
import re
from frontier import BASE, POOLS, read, measure, sha256

def bounds():
    default={}
    known=defaultdict(set)
    unknown={}
    for folder in POOLS:
        for r in read(BASE/folder/"FROZEN.json")["rows"]:
            if r["benchmark"]=="BenchPreS":
                default[r["uid"]]=r
        for v in read(BASE/folder/"RESULTS.json")["rows"]:
            if v["benchmark"]!="BenchPreS" or not v["answer"]:
                continue
            u=v["uid"]
            h=sha256(v["answer"].encode()).hexdigest()
            if v.get("score"):
                known[u].add(h)
            else:
                unknown[u,h]=(folder,v)
    attrs=read(BASE/POOLS[0]/"BENCH_PARTIAL.json")["attribute_rows"]
    result=[]
    for (u,h),(folder,v) in unknown.items():
        base=default[u]
        s=measure("BenchPreS","communication",base["base_score"])
        if h in known[u] or h==base["baseline_answer_sha256"] or s["positions"]==s["primary"]:
            continue
        assert folder==POOLS[0]
        labels=[(x["appropriate"],x["labels"][v["method"]]) for x in attrs if x["uid"]==u]
        assert len(labels)==5
        aar_max=sum(a and label!="do_not_follow" for a,label in labels)
        mr_min=sum(not a and label=="follow" for a,label in labels)
        text=v["raw_scores"].get("BenchComplete") or ""
        match=re.search(r"Rating:\s*\[\[([1-5])\]\]\s*$",text)
        complete_max=int(match[1]) if match else 5
        possible=aar_max>s["primary"] and mr_min<=s["MR"] and complete_max>=s["completeness"]
        result.append({"aar_gain_max":aar_max-s["primary"],"mr_change_min":mr_min-s["MR"],
                       "completeness_change_max":complete_max-s["completeness"],"potential_protected_gain":possible,
                       "receipts":dict(Counter(v["judge_statuses"].values()))})
    return result

if __name__=="__main__":print(json.dumps(bounds(),indent=2))
