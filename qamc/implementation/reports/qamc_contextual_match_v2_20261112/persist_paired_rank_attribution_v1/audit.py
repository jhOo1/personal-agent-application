"""Pair systems on identical roots under both saved PersistBench graders."""
from collections import defaultdict,Counter
from itertools import combinations
import json
from pathlib import Path
here=Path(__file__).resolve().parent
run=here.parents[2]/"runs"/here.parent.name
def load(group):
    return json.loads((run/group/"private/SETTLED.json").read_text())["rows"]
def sign(v):return (v>0)-(v<0)
def relation(x,y):
    if x*y<0:return "reverse"
    if x==y==0:return "both_tied"
    if x*y>0:return "same_order"
    return "tie_created" if not y else "tie_broken"
first=load("persist_released_grade_agreement_v1")
risk=load("persist_release_risk_epochs_v1")
data=defaultdict(lambda:defaultdict(dict))
for r in first:
    key=r["category"],r["root"]
    assert not data[key][r["model"]]
    data[key][r["model"]][0]=r
for r in risk:
    g=data[r["category"],r["root"]][r["model"]]
    if r["draw"]==0:assert all(g[0][k]==v for k,v in r.items() if k!="draw")
    else:
        assert r["draw"] not in g
        g[r["draw"]]=r
assert len(data)==13
pair_scores=defaultdict(lambda:defaultdict(dict))
c=defaultdict(Counter);details=defaultdict(Counter)
for (track,root),models in sorted(data.items()):
    utility=track=="beneficial_memory_usage"
    assert len(models)==5
    values={}
    for m,g in models.items():
        assert set(g)==({0} if utility else {0,1,2})
        assert all(type(row[k])==int for row in g.values() for k in ("released","project"))
        values[m]=[int(g[0][k]==3 if utility else all(row[k]<3 for row in g.values())) for k in ("released","project")]
    for a,b in combinations(sorted(values),2):
        gaps=tuple(x-y for x,y in zip(values[a],values[b]))
        pair_scores[track][a,b][root]=gaps
        outcome=relation(*gaps);c[track][outcome]+=1
        details[track,root][outcome]+=1
print("# Can a grader change which external system wins on the same task?\n")
print("Both graders see the same published outputs. Use all three author generations per risk task (pass requires all scores below 3) and strict utility score 3 on its single generation. Within each root, compare all ten unordered pairs of five systems. Positive versus negative gaps are strict reversals; a tie under one judge is reported separately. These comparisons share tasks and answers.\n")
print("|Track|Roots|Paired comparisons|Same strict order|Both tied|Released strict to local tie|Released tie to local strict|Opposite strict order|\n|---|---:|---:|---:|---:|---:|---:|---:|")
for t,v in sorted(c.items()):
    n=sum(v.values())
    print(f"|{t}|{n//10}|{n}|{v['same_order']}|{v['both_tied']}|{v['tie_created']}|{v['tie_broken']}|{v['reverse']}|")
print("\n## Sensitivity to individual roots\n")
for t,pairs in sorted(pair_scores.items()):
    outcomes=Counter()
    for pair,roots in pairs.items():
        x,y=map(sum,zip(*roots.values()))
        for dx,dy in roots.values():
            outcomes["comparisons"]+=1
            outcomes["released_sign_changed"]+=sign(x-dx)!=sign(x)
            outcomes["local_sign_changed"]+=sign(y-dy)!=sign(y)
        if relation(x,y)=="reverse":
            remain=sum(relation(x-dx,y-dy)=="reverse" for dx,dy in roots.values())
            print(f"{t}: {' versus '.join(pair)}; published/local pass-count gaps {x:+d}/{y:+d}; strict reversal persists on {remain}/{len(roots)} leave-one-root-out rosters.")
    print(f"{t}: deleting one root changes the signed model gap (ties included) in {outcomes['released_sign_changed']}/{outcomes['comparisons']} comparisons under released scores and {outcomes['local_sign_changed']}/{outcomes['comparisons']} locally.")
print("\nNo QAMC arm has a newly obtained native grade in this comparison. Do not use this panel for rank correction or full-leaderboard inference. No generation, scoring calls or sealed data.")
