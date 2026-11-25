"""Summarize common native denominators and the cost of missing answers."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

ARMS=("BASE","FREE","TATR")
HERE=Path(__file__).resolve().parent
BOLD=re.compile(r"\bbold\s+text\b",re.I)


def measure(benchmark,stratum,s):
    if benchmark=="RPEval":
        if not s or any(k not in s for k in ("match","OPB","UPB","FM")):
            return None
        return {"primary":s["match"]["matched"],"positions":s["match"]["positions"],
                **{k:s[k] for k in ("OPB","UPB","FM")}}
    if benchmark=="BenchPreS":
        if not s or any(k not in s for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator",
                                             "task_completeness","decisions")):
            return None
        return {"primary":s["aar_numerator"],"positions":s["aar_denominator"],"MR":s["mr_numerator"],
                "MR_denominator":s["mr_denominator"],"completeness":s["task_completeness"],
                "nonbold":sum(x["appropriate"] and x["label"]=="follow" and not BOLD.search(x["preference"])
                              for x in s["decisions"]),
                "nonbold_denominator":sum(x["appropriate"] and not BOLD.search(x["preference"]) for x in s["decisions"])}
    if not s or any(type(s.get(k)) is not bool for k in ("failure_release","failure_strict_utility")):
        return None
    return {"primary":int(not s["failure_release"]),"strict_pass":int(not s["failure_strict_utility"]),
            "positions":1}


def aligned(cells,arms):
    active=[cells[a] for a in arms]
    if not all(active):
        return False
    for key in ("positions","MR_denominator","nonbold_denominator"):
        if len({m.get(key) for m in active})!=1:
            raise ValueError("Native position denominators diverged")
    return True


def bounds(rows,left,right):
    low=high=0
    for card,_,values in rows:
        cap=values["BASE"]["positions"]
        x,y=values[left],values[right]
        low+=(x["primary"] if x else 0)-(y["primary"] if y else cap)
        high+=(x["primary"] if x else cap)-(y["primary"] if y else 0)
    return [low,high]


def group(rows):
    pieces=defaultdict(list)
    for triple in rows:
        card,_,_=triple
        key=card["benchmark"]
        pieces[key].append(triple)
        pieces[key+"/"+card["stratum"]].append(triple)
        if key=="RPEval":
            pieces[key+("/diagnostic" if card["diagnostic"] else "/hashed")].append(triple)
    return pieces


def paired(rows,arms,unflagged=False):
    n=0
    metric=defaultdict(Counter)
    for card,receipts,values in rows:
        if not aligned(values,arms):
            continue
        if unflagged and card["benchmark"]=="RPEval" and any((
                card["base_flags"] if a=="BASE" else receipts[a].get("score_flags"))!=[] for a in arms):
            continue
        n+=1
        for a in arms:
            metric[a].update(values[a])
    return {"n":n,"metrics":metric}


def summarize(pin,outcome):
    received={(r["uid"],r["method"]):r for r in outcome["rows"]}
    cards=[]
    for c in pin["rows"]:
        filled={a:received[c["uid"],a] for a in ARMS if a!="BASE"}
        grade = {"BASE":c["base_score"],**{a:x["score"] for a,x in filled.items()}}
        values={a:measure(c["benchmark"],c["stratum"],score) for a,score in grade.items()}
        if values["BASE"] is None:
            raise ValueError("No usable strong reference grade")
        cards.append((c,filled,values))
    summary={}
    for key,rows in group(cards).items():
        by_arm = {}
        for a in ARMS[1:]:
            chosen=[r[a] for _,r,_ in rows]
            ctr=Counter(r["disposition"] for r in chosen)
            ctr["delivered"]=sum(r["actor_status"]=="OK" for r in chosen)
            ctr["usable_grades"]=sum(v[a] is not None for _,_,v in rows)
            ctr["at_least_one_anchor"]=sum(bool(c["packet"]["protected_literals"]) for c,_,_ in rows)
            ctr["unchanged_base_score_reuse"]=sum(r.get("score_origin")=="EXACT_BASE" for r in chosen)
            ctr["actual_revision_has_program_copy"]=sum(r["disposition"]=="REVISED" and (
                (r.get("operation_stats",{}).get("program") or {}).get("copied_chars",0)>0) for r in chosen)
            ctr["actual_tatr_revision_has_no_program_copy"]=sum(a=="TATR" and r["disposition"]=="REVISED" and
                r["operation_stats"]["program"]["copied_chars"]==0 for r in chosen)
            stats=[r["operation_stats"] for r in chosen if r.get("operation_stats")]
            by_arm[a]={"statuses":ctr,"aligned_characters":sum(s["aligned_characters"] for s in stats),
                       "aligned_reference_characters":sum(s["base_characters"] for s in stats),
                       "answer_characters":sum(s["answer_characters"] for s in stats),
                       "direct_copy_characters":sum((s["program"] or {}).get("copied_chars",0) for s in stats),
                       "written_characters":sum((s["program"] or {}).get("written_chars",0) for s in stats)}
        summary[key]={"assigned":len(rows),"by_arm":by_arm,"common":paired(rows,ARMS),
                      "unflagged_common":paired(rows,ARMS,True),
                      "separate_pairs":{a:paired(rows,("BASE",a)) for a in ARMS[1:]},
                      "missing_primary_delta_bounds":{a+"-"+b:bounds(rows,a,b)
                                                     for a,b in (("TATR","FREE"),("FREE","BASE"),("TATR","BASE"))}}
    diffs=[]
    for c,receipts,values in cards:
        diffs.append({"uid":c["uid"],"benchmark":c["benchmark"],"group":c["group"],"stratum":c["stratum"],
                      "diagnostic":c["diagnostic"],"scores":values,
                      "dispositions":{a:receipts[a]["disposition"] for a in ARMS[1:]}})
    return {"breakdowns":summary,"per_task":diffs,"calls":outcome["calls"],"statuses":outcome["statuses"],
            "tokens":outcome["tokens"],"usage_unknown":outcome["usage_unknown"]}


if __name__=="__main__":
    print(json.dumps(summarize(json.loads((HERE/"FROZEN.json").read_text()),
                               json.loads((HERE/"RESULTS.json").read_text())),ensure_ascii=False,indent=2))
