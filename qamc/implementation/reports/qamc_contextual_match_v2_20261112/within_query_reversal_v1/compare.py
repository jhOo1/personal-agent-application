"""Does the archived IPE-C decision distinguish opposite winning histories?"""
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from statistics import mean

base = Path(__file__).resolve().parents[1]
def records(file):
    return json.loads((base / file).read_text())["rows"]

hashes = {r["uid"]: r.get("task_only_request_sha256") for r in records("ipe_c_full_exposed_panel_v1/FROZEN.json")}
data = records("ipe_c_two_endpoint_completion_v1/RESULTS.json")
assert len({r["uid"] for r in data}) == len(hashes) == 300
print("# Can the switch route both histories correctly when the same task changes its preferred endpoint?\n")
print("Group the 300 exposed assignments by exact frozen empty-history Actor request. Eligible rows require graded full, empty and deployed endpoints and agreement on the deployed answer hash. A reversal pair has a strict full-history Match win on one assignment and a strict empty-history win on the other. Tied endpoint scores never establish a reversal. Reversals are identified retrospectively.\n")
print("|Subset|Eligible tasks|Request groups|Groups with reversals|Reversal pairs|Both correct|Both wrong|Same route|Macro both correct|Macro equal-rate reference|")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for name in ("All", "Both endpoints unflagged", "Neither history has author C", "Additional 67 only"):
    groups = defaultdict(list)
    for r in data:
        if name == "Additional 67 only" and r["scope"] != "additional_67":
            continue
        wire = hashes[r["uid"]]
        cells = r["scores"]
        endpoints = ("IPE_C", "RPR_PAPER_FULL", "TASK_ONLY")
        if not wire or any(not ((cells.get(k) or {}).get("grade") or {}).get("match") for k in endpoints):
            continue
        on = r["old_route"]=="REUSE_RP"
        assert cells["IPE_C"]["answer_sha256"] == cells["RPR_PAPER_FULL" if on else "TASK_ONLY"]["answer_sha256"]
        full,empty = [cells[k] for k in ("RPR_PAPER_FULL","TASK_ONLY")]
        if name.startswith("Both") and (full["flags"] != [] or empty["flags"] != []):
            continue
        if name.startswith("Neither") and "C" in r["labels"]:
            continue
        gap = full["grade"]["match"]["matched"]-empty["grade"]["match"]["matched"]
        groups[wire].append((gap,on))
    success=wrong=partial=0
    rates=[]; expected=[]
    for g in groups.values():
        flips=[(a,b) for a,b in combinations(g,2) if a[0]*b[0]<0]
        if not flips:
            continue
        correct=[sum((gap>0)==on for gap,on in pair) for pair in flips]
        success+=correct.count(2)
        wrong+=correct.count(0)
        partial+=correct.count(1)
        rates.append(correct.count(2)/len(correct))
        n=len(g); k=sum(on for _,on in g)
        expected.append(k*(n-k)/(n*(n-1)))
    print(f"|{name}|{sum(map(len,groups.values()))}|{len(groups)}|{len(rates)}|{success+wrong+partial}|{success}|{wrong}|{partial}|{mean(rates):.1%}|{mean(expected):.1%}|")
print("\nMacro averages give each request group with reversals one vote. The reference randomly redistributes its observed number of history-on routes among all eligible histories in that group. Pair counts reuse histories and do not count independent replications. No author labels enter IPE-C. No new model calls.")
