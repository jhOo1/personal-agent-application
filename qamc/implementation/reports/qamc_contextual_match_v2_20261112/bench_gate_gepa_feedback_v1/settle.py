"""Read-only aggregate report. Case-level receipts remain private."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs" / HERE.parent.name / HERE.name
ARMS = ("baseline", "score", "behavior")


def read(path):
    return json.loads(path.read_text())


def totals(scores):
    m = Counter()
    for s in scores:
        for k in ("aar_numerator","aar_denominator","mr_numerator","mr_denominator","task_completeness"):
            m[k] += s[k]
        for d in s["decisions"]:
            if d["appropriate"] and "bold" not in d["preference"].lower():
                m["nonbold_denominator"] += 1
                m["nonbold_numerator"] += d["label"] == "follow"
    return dict(m)


def report():
    f=read(RUN/"material/FROZEN.json")
    settled=read(RUN/"material/SETTLED.json")
    plan=read(RUN.with_name("benchpres_repeat_matched_v1")/"PLAN_PRIVATE.json")
    groups={r["uid"]:r["analysis_group_id"] for r in plan["cases"]}
    rows={(r["uid"],r["arm"]):r for r in settled["rows"]}
    assert len(rows)==len(settled["rows"]) and set(f["folds"])==set(groups)
    common=sorted(u for u in groups if all(rows.get((u,a),{}).get("score") is not None for a in ARMS))
    def block(ids):
        return {"tasks":len(ids),"arms":{a:totals(rows[u,a]["score"] for u in ids) for a in ARMS}}
    by_profile={g:block([u for u in common if groups[u]==g]) for g in sorted(set(groups.values()))}
    by_fold={i:block([u for u in common if f["folds"][u]==i]) for i in (0,1)}
    profile_differences={}
    for control in ("score","baseline"):
        for n,d in (("nonbold_numerator","nonbold_denominator"),("aar_numerator","aar_denominator"),("mr_numerator","mr_denominator"),("task_completeness",None)):
            diffs=[]
            for group in by_profile.values():
                if not group["tasks"]:continue
                scores=group["arms"]
                denom=scores["behavior"].get(d,0) if d else group["tasks"]
                if denom:
                    if d: assert scores[control].get(d,0)==denom
                    diffs.append((scores["behavior"].get(n,0)-scores[control].get(n,0))/denom)
            profile_differences[f"behavior_minus_{control}_{n}"]={"profiles":len(diffs),"mean":sum(diffs)/len(diffs) if diffs else None}
    statuses=Counter()
    usage=Counter()
    unknown=0
    for p in RUN.glob("*/visible/*/record.json"):
        rec=read(p)
        statuses[rec["status"]]+=1
        if not isinstance(rec.get("usage"),dict) or rec["usage"].get("total_tokens") is None:unknown+=1
        else:usage["total_tokens"]+=rec["usage"]["total_tokens"]
    return {"assigned":len(groups),"original_wires":len(f["wire_hashes"]),"all_three":block(common),
            "complete_scores":{a:sum(rows.get((u,a),{}).get("score") is not None for u in groups) for a in ARMS},
            "folds":by_fold,"profile_mean_differences":profile_differences,"transport":dict(statuses),
            "reported_usage":dict(usage),"unknown_usage":unknown}


if __name__=="__main__":print(json.dumps(report(),indent=2))
