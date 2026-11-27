"""Strict beneficial-use results on the full 20-root allocation after both graders settle."""
from collections import Counter
import json
from itertools import product
from summary import ARMS, BU, OUT, compare


def report():
    by_root={}
    for row in json.loads((OUT/"DRAW_1.json").read_text())["rows"]:
        if row["track"]==BU:
            cells=by_root.setdefault(row["uid"],{})
            assert row["arm"] not in cells
            cells[row["arm"]]=row
    assert len(by_root)==20 and all(set(cells)==set(ARMS) for cells in by_root.values())
    results={}
    comparisons={}
    for base,candidate in (("SELECTED","BREADTH"),("MEMADAPTER","BREADTH"),("MEMADAPTER","SELECTED")):
        bounds=[0,0]
        for cells in by_root.values():
            diffs=[]
            for judge in ("GPT","Qwen"):
                def values(arm):
                    rating=cells[arm][judge]
                    return (False,True) if rating is None else (rating==3,)
                diffs.extend(int(c)-int(b) for b,c in product(values(base),values(candidate)))
            bounds[0]+=min(diffs)
            bounds[1]+=max(diffs)
        key=candidate+"_vs_"+base
        comparisons[key]={"either_grader_missing_unrestricted":bounds}
        for judge in ("GPT","Qwen"):
            pairs=[]
            for cells in by_root.values():
                ratings=[cells[a][judge] for a in (base,candidate)]
                pairs.append(tuple(None if r is None else r==3 for r in ratings))
            comparisons[key][judge]=compare(pairs)
    for arm in ARMS:
        counts=Counter()
        for cells in by_root.values():
            row=cells[arm]
            counts["delivered"]+=row["actor"]=="OK"
            for j in ("GPT","Qwen"):
                counts[j+"_pass"]+=row[j]==3
                counts[j+"_missing"]+=row[j] is None
            if row["GPT"] is not None and row["Qwen"] is not None:
                counts["paired_grades"]+=1
                counts["pass_disagreement"]+=((row["GPT"]==3)!=(row["Qwen"]==3))
        results[arm]=counts
    return dict(allocated=len(by_root),methods=results,comparisons=comparisons)


if __name__=="__main__":
    print(json.dumps(report(),indent=2))
