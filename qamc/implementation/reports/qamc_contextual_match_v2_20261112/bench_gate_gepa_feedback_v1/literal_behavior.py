"""Read-only surface diagnostics, on the three-arm intersection of actual answers."""
from collections import Counter
from statistics import median
import json
import re
from settle import ARMS, ROOT, RUN, read

def main():
    guide=read(RUN.with_name("benchpres_repeat_matched_v1")/"PLAN_PRIVATE.json")
    answers={}
    for p in (RUN/"Actor").glob("visible/*/record.json"):
        r=read(p)
        if r["status"]!="OK":continue
        k=(r["unit"]["root_id"],r["unit"]["method"])
        if k in answers:raise ValueError("Duplicate case")
        answers[k]=read(p.with_name("response.json"))["answer"]
    out={a:Counter() for a in ARMS}
    lengths={a:[] for a in ARMS}
    pairs={a:Counter() for a in ARMS if a!="baseline"}
    count=0
    for c in guide["cases"]:
        u=c["uid"]
        if not all((u,a) in answers for a in ARMS):continue
        count+=1
        ref=read(ROOT/c["evaluation_path"])
        for a in ARMS:
            answer=answers[u,a]
            lengths[a].append(len(answer))
            for pref,allowed in zip(ref["preference_attribute"],ref["preference_label"],strict=True):
                nick=re.search(r'called "([^"]+)"',pref)
                if nick:
                    kind="nickname"
                    hit=re.search(r"(?<!\w)"+re.escape(nick[1])+r"(?!\w)",answer) is not None
                elif "bold" in pref.lower():
                    kind="markdown_bold"
                    hit=re.search(r"\*\*[^*\n]*[^\s*][^*\n]*\*\*",answer) is not None
                else:continue
                key=("appropriate_" if allowed else "inappropriate_")+kind
                out[a][key+"_positions"]+=1
                out[a][key+"_hits"]+=int(hit)
            if a!="baseline":
                b=len(answers[u,"baseline"])
                pairs[a]["shorter" if len(answer)<b else "longer" if len(answer)>b else "equal"]+=1
    return {"common_deliveries":count,"per_arm":out,"median_characters":{a:median(v) if v else None for a,v in lengths.items()},
            "length_vs_baseline":pairs,"median_paired_length_change":{a:median([v-b for v,b in zip(lengths[a],lengths["baseline"],strict=True)]) if count else None for a in pairs}}

if __name__=="__main__":print(json.dumps(main(),indent=2))
