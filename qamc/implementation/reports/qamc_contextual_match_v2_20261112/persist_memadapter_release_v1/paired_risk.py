"""Source-level pairing with one shared unknown for a shared Actor draw and grader."""
import json
from collections import Counter
from itertools import product

from case_answers import assemble
from competition import BU, OUT, inputs, read


def allowed(values):
    return (False,True) if values is None else (values,)


def draw_options(baseline,candidate,shared):
    values=set(product(allowed(baseline),allowed(candidate)))
    if shared:
        values={pair for pair in values if pair[0]==pair[1]}
    if not values:
        raise ValueError("A shared exact Actor and grader has incompatible outcomes")
    return values


def change_set(draws):
    return {int(all(x[1] for x in combination))-int(all(x[0] for x in combination))
            for combination in product(*draws)}


def analyze():
    _,cases,tasks=inputs()
    grades={}
    actors={}
    for d in (1,2,3):
        data=read(OUT/f"DRAW_{d}.json")
        prefixes={u.split("/")[-1][:8] for u,c in cases.items() if d==1 or c["category"]!=BU}
        actors[d]=assemble(d,cases,tasks,prefixes)
        for row in data["rows"]:
            key=d,row["uid"],row["arm"]
            assert key not in grades and row["draw"]==d
            grades[key]=row
    result={}
    for base,candidate in (("SELECTED","BREADTH"),("MEMADAPTER","BREADTH"),("MEMADAPTER","SELECTED")):
        counts={}
        examples={}
        for uid,c in cases.items():
            cat=c["category"]
            prefix=uid.split("/")[-1][:8]
            judges={}
            for j in ("GPT","Qwen"):
                draws=[]
                for d in ((1,) if cat==BU else (1,2,3)):
                    arms=actors[d][prefix]["arms"]
                    shared=bool(arms[base].get("actor_digest") and arms[base]["actor_digest"]==arms[candidate].get("actor_digest"))
                    scores=[grades[d,uid,a][j] for a in (base,candidate)]
                    pair=[None if g is None else (g==3 if cat==BU else g<3) for g in scores]
                    draws.append(draw_options(*pair,shared))
                judges[j]=change_set(draws)
            outcomes=judges["GPT"]|judges["Qwen"]
            cnt=counts.setdefault(cat,Counter())
            cnt["allocated"]+=1
            cnt["net_lower"]+=min(outcomes)
            cnt["net_upper"]+=max(outcomes)
            label=("robust_win" if outcomes=={1} else "robust_loss" if outcomes=={-1}
                   else "forced_tie" if outcomes=={0} else "ambiguous")
            cnt[label]+=1
            if label in ("robust_win","robust_loss"):
                examples[prefix]=label
        result[candidate+"_vs_"+base]=dict(tracks=counts,unambiguous_differences=examples)
    return result


if __name__=="__main__":
    print(json.dumps(analyze(),indent=2))
