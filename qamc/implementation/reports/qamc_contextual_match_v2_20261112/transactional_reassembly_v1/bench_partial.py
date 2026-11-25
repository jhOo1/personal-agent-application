"""Diagnostic paired scoring of individually observed BenchPreS fields."""
from collections import Counter
import json
import re

from baselines import archive, HERE
from qamc.common import parse_object
from qamc.pa.core import digest

ARMS=("BASE","FREE","TATR")
RATING=re.compile(r"Rating:\s*\[\[([1-5])\]\]\s*$")


def field(cell, idx, base=False):
    if (score:=cell.get("base_score" if base else "score")) is not None:
        return (score["task_completeness"] if idx=="complete" else score["decisions"][idx]["label"])
    key="BenchComplete" if idx=="complete" else f"BenchAttr{idx}"
    raw=cell.get("raw_scores",{}).get(key)
    if not raw:
        return None
    try:
        if idx=="complete":
            m=RATING.search(raw)
            return int(m.group(1)) if m else None
        label=parse_object(raw).get("label")
        return label if label in ("follow","do_not_follow") else None
    except (AttributeError,ValueError,TypeError):
        return None


def diagnose():
    cases,_,_=archive.transfer.context("BenchPreS")
    plan=archive.read(HERE/"FROZEN.json")
    outcomes={(r["uid"],r["method"]):r for r in archive.read(HERE/"RESULTS.json")["rows"]}
    diagnostic=Counter()
    categories={}
    attribute_rows=[]
    for c in plan["rows"]:
        if c["benchmark"]!="BenchPreS":
            continue
        uid=c["uid"]
        case=cases[uid]
        ref=archive.read(archive.transfer.bench.ROOT/case["evaluation_path"])
        if digest(ref)!=case["evaluation_hash"]:
            raise ValueError("Changed evaluation attributes")
        arms=[c,*(outcomes[uid,a] for a in ARMS[1:])]
        for i,(pref,appropriate) in enumerate(zip(ref["preference_attribute"],ref["preference_label"],strict=True)):
            labels=dict(zip(ARMS,(field(row,i,idx==0) for idx,row in enumerate(arms)),strict=True))
            category=("AAR_bold" if re.search(r"\bbold\s+text\b",pref,re.I) else "AAR_nonbold") if appropriate else "MR"
            attribute_rows.append({"uid":uid,"preference":pref,"appropriate":appropriate,"labels":labels})
            diagnostic[category+"_assigned"]+=1
            cat=categories.setdefault(category,Counter())
            if all(label is not None for label in labels.values()):
                cat["common_positions"]+=1
                for a,label in labels.items():
                    cat[a]+=label=="follow"
        values=dict(zip(ARMS,(field(row,"complete",i==0) for i,row in enumerate(arms)),strict=True))
        if all(v is not None for v in values.values()):
            cat=categories.setdefault("completeness",Counter())
            cat["common_positions"]+=1
            cat.update(values)
    return {"diagnostic_only":True,"assigned":diagnostic,"common":categories,
            "attribute_rows":attribute_rows,"new_requests":0}


if __name__=="__main__":
    print(json.dumps(diagnose(),ensure_ascii=False,indent=2))
