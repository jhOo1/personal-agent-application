"""Read both frozen deployments; compare endpoint grades without weighting fields."""
from collections import Counter
import json
from pathlib import Path

here = Path(__file__).resolve().parent
base = here.parents[2]/"runs"/here.parent.name/"rpe_ipe_fresh_repeat_v1"
runs = []
for i in (1, 2):
    rows = json.loads((base/f"deployment{i}"/"RESULTS.json").read_text())["rows"]
    by_root = {r["group"]:r for r in rows}
    assert len(by_root) == len(rows) == 18
    runs.append(by_root)
assert runs[0].keys() == runs[1].keys()


def delta(row, comparator):
    grades = [row["scores"].get(arm, {}).get("grade", {}) for arm in (row["branch"], comparator)]
    if not all(isinstance(g.get("match"), dict) and all(isinstance(g.get(k), (int,float)) for k in ("OPB","UPB","FM")) for g in grades):
        return None
    matches = [g["match"] for g in grades]
    if any(m.get("matched") is None for m in matches):
        return None
    assert matches[0]["positions"] == matches[1]["positions"]
    assert all(0<=m["matched"]<=m["positions"] for m in matches)
    a,b=grades
    return (matches[0]["matched"]-matches[1]["matched"],
            *(b[k]-a[k] for k in ("OPB","UPB","FM")))


def direction(d):
    if d is None: return "unknown"
    if not any(d): return "tie"
    if min(d)>=0: return "better"
    if max(d)<=0: return "worse"
    return "tradeoff"


print("# Joint outcomes across two fresh RPEval deployments\n")
print("Better means at least one improvement with no deterioration over Match count, OPB, UPB and FM. Severity decreases are favorable. Mixed directions are tradeoffs. Missing fields remain unknown.\n")
print("|Comparator|First draw|Second draw|Roots|\n|---|---|---|---:|")
details=[]
for comparator in ("RP_FULL","TASK_ONLY"):
    counts=Counter()
    for root,r in sorted(runs[0].items()):
        s=runs[1][root]
        assert (r["uid"],r["stratum"])==(s["uid"],s["stratum"])
        shifts=[delta(row,comparator) for row in (r,s)]
        key=tuple(map(direction,shifts))
        counts[key]+=1
        if key in (("better","better"),("worse","worse"),("tradeoff","tradeoff")):
            details.append((comparator,r["uid"],r["stratum"],*key,*shifts))
    for (a,b),n in sorted(counts.items()): print(f"|{comparator}|{a}|{b}|{n}|")
print("\n## Repeated non-tie directions\n")
print("|Comparator|Exposed task|Stratum|Direction|First delta|Second delta|\n|---|---|---|---|---|---|")
for c,u,s,a,_,x,y in details:
    print(f"|{c}|{u}|{s}|{a}|{x}|{y}|")

print("\n## Symmetric scoring-flag sensitivity\n")
print("Keep a root only when both routes have complete four-field comparisons and neither endpoint has an archived scoring flag in either deployment. Same population for both comparisons.\n")
valid = [root for root in runs[0] if all(
    all(row["scores"][arm].get("flags") == [] for arm in ("TASK_ONLY","RP_FULL"))
    and all(delta(row, arm) is not None for arm in ("TASK_ONLY","RP_FULL"))
    for row in (runs[0][root],runs[1][root]))]
print("|Comparator|Eligible roots|Better twice|Worse twice|Mixed fields twice|\n|---|---:|---:|---:|---:|")
for arm in ("RP_FULL","TASK_ONLY"):
    cnt=Counter(tuple(direction(delta(run[root],arm)) for run in runs) for root in valid)
    print(f"|{arm}|{len(valid)}|{cnt['better','better']}|{cnt['worse','worse']}|{cnt['tradeoff','tradeoff']}|")
