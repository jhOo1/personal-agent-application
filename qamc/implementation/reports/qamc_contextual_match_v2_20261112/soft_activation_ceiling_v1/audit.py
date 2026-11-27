"""Measure how much each direction of a switch could gain on saved soft-only outcomes."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
panel = json.loads((root / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]
eligible = [r for r in panel if "B" in (r["labels"] or "") and "C" not in r["labels"]]
assert len(panel) == 300 and len(eligible) == 54
print("# Remaining endpoint-choice opportunities on B-present, C-absent RPEval tasks\n")
print("Use every labeled soft-only task in the exposed 300-task archive. A protected switch must strictly improve Match on that same task and weakly reduce each OPB, UPB and FM severity. Each action is applied only to the fixed IPE-C branch it would change. The oracle sees scores and author strata and is ineligible for deployment.\n")
print("|Grade filter|Direction|Paired tasks|Positions|IPE-C Match|Always switch Match|Switch wins/losses/ties|Best possible extra Match|Protected extra Match|Protected wins/groups|")
print("|---|---|---:|---:|---:|---:|---|---:|---:|---:|")
protected_cases = []
for clean in (False,True):
    for keep_history in (False,True):
        pairs=[]
        for row in eligible:
            if (row["old_route"] == "REUSE_RP") != keep_history:
                continue
            old = row["scores"]["IPE_C"]
            full = row["scores"]["RPR_PAPER_FULL"]
            off = row["scores"]["TASK_ONLY"]
            if any(not ((e or {}).get("grade") or {}).get("match") for e in (old,full,off)):
                continue
            if clean and any(e["flags"] != [] for e in (old,full,off)):
                continue
            orig,alt = (full,off) if keep_history else (off,full)
            assert old["answer_sha256"] == orig["answer_sha256"] and old["grade"]==orig["grade"]
            a,b=orig["grade"],alt["grade"]
            assert a["match"]["positions"]==b["match"]["positions"]==len(row["labels"])
            delta=b["match"]["matched"]-a["match"]["matched"]
            protected=delta>0 and all(b[k]<=a[k] for k in ("OPB","UPB","FM"))
            if protected and not clean:
                protected_cases.append((row["uid"], a["match"]["matched"], b["match"]["matched"], len(row["labels"]), all(e["flags"]==[] for e in (old,full,off))))
            pairs.append((a["match"]["matched"],delta,len(row["labels"]),protected,row["source_group"]))
        wins=sum(d>0 for _,d,_,_,_ in pairs)
        losses=sum(d<0 for _,d,_,_,_ in pairs)
        baseline=sum(a for a,*_ in pairs)
        gains=[d for _,d,_,_,_ in pairs]
        guarded=[(d,g) for _,d,_,ok,g in pairs if ok]
        line=["unflagged" if clean else "all", "close" if keep_history else "reopen",len(pairs),
              sum(p[2] for p in pairs),baseline,baseline+sum(gains),f"{wins}/{losses}/{len(pairs)-wins-losses}",
              sum(max(0,d) for d in gains),sum(d for d,_ in guarded),f"{len(guarded)}/{len(set(g for _,g in guarded))}"]
        print("|"+"|".join(map(str,line))+"|")
print("\nGroup counts use the archived source group. The two directions may share groups. The protected ceiling concerns grader severities, not independent task fidelity. Values represent saved generations, not bounds on newly generated answers. No new calls.")

print("\nProtected cases (IPE-C to alternative):")
for uid,before,after,n,clean in protected_cases:
    print(f"- {uid}: {before} to {after} of {n}; both endpoints unflagged: {clean}")
