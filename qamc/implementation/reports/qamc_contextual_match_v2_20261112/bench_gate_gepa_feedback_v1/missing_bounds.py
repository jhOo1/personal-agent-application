"""Bounds for the behavior arm's paired differences using complete case grades."""
from collections import defaultdict
import json
from settle import ROOT, RUN, read


def outcome_range(reference, score):
    attrs = list(zip(reference["preference_label"], reference["preference_attribute"], strict=True))
    masks = {
        "AAR": [i for i,(allowed,_) in enumerate(attrs) if allowed],
        "nonbold_AAR": [i for i,(allowed,a) in enumerate(attrs) if allowed and "bold" not in a.lower()],
        "MR": [i for i,(allowed,_) in enumerate(attrs) if not allowed],
    }
    if score:
        decisions = score["decisions"]
        assert [(d["appropriate"],d["preference"]) for d in decisions] == attrs
        counts = {key:sum(decisions[i]["label"]=="follow" for i in pos) for key,pos in masks.items()}
        out = {key:(count,count,len(masks[key])) for key,count in counts.items()}
        c = score["task_completeness"]
        assert 1 <= c <= 5
        out["completeness"] = (c,c,1)
    else:
        out = {key:(0,len(pos),len(pos)) for key,pos in masks.items()}
        out["completeness"] = (1,5,1)
    return out


def bounds(plan, uids, scores):
    result = {}
    for arm in ("score","baseline"):
        sums = defaultdict(lambda: [0,0,0])
        for case in plan["cases"]:
            u=case["uid"]
            if u not in uids:continue
            ref=read(ROOT/case["evaluation_path"])
            a=outcome_range(ref,scores.get((u,"behavior")))
            b=outcome_range(ref,scores.get((u,arm)))
            for metric,(low,high,den) in a.items():
                other_low,other_high,other_den=b[metric]
                assert den==other_den
                acc=sums[metric]
                acc[0]+=low-other_high
                acc[1]+=high-other_low
                acc[2]+=den
        result["behavior_minus_"+arm]={m:dict(lower=v[0],upper=v[1],denominator=v[2]) for m,v in sums.items()}
    return result


def report():
    plan=read(RUN.with_name("benchpres_repeat_matched_v1")/"PLAN_PRIVATE.json")
    f=read(RUN/"material/FROZEN.json")
    scores={(r["uid"],r["arm"]):r["score"] for r in read(RUN/"material/SETTLED.json")["rows"]}
    return {key:bounds(plan,set(ids),scores) for key,ids in
            (("eligible",f["wire_hashes"]),("original_assignment",f["folds"]))}


if __name__=="__main__":print(json.dumps(report(),indent=2))
