"""Partition the previously reported no-C reversal pairs without resampling."""
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

base = Path(__file__).resolve().parents[1]
def rows(path):
    return json.loads((base / path).read_text())["rows"]

wires = {r["uid"]:r.get("task_only_request_sha256") for r in rows("ipe_c_full_exposed_panel_v1/FROZEN.json")}
groups = defaultdict(list)
for r in rows("ipe_c_two_endpoint_completion_v1/RESULTS.json"):
    uid = r["uid"]
    if not wires[uid] or not r["labels"] or "C" in r["labels"]:
        continue
    scores = r["scores"]
    if any(not ((scores.get(k) or {}).get("grade") or {}).get("match") for k in ("RPR_PAPER_FULL","TASK_ONLY","IPE_C")):
        continue
    full, empty = [scores[k] for k in ("RPR_PAPER_FULL","TASK_ONLY")]
    gap = full["grade"]["match"]["matched"] - empty["grade"]["match"]["matched"]
    groups[wires[uid]].append((uid, r["labels"], gap, full["flags"] == [] and empty["flags"] == [],empty["answer_sha256"]))

print("# Histories behind the ten no-C reversals\n")
print("Each row contrasts two histories with one identical task-only Actor request. Gap is full-history minus empty-history matched positions. Clean requires no recorded flags for either endpoint on either history. A clean grade can still contain an attribution error.\n")
print("|Full wins on|Author labels|Gap|Empty wins on|Author labels|Gap|Both clean|Same empty answer|")
print("|---|---|---:|---|---|---:|---|---|")
total = 0
for group in groups.values():
    for a,b in combinations(group,2):
        if a[2]*b[2]>=0:
            continue
        pos,neg = sorted((a,b),key=lambda x:x[2],reverse=True)
        total+=1
        print(f"|{pos[0].removeprefix('rpeval/')}|{pos[1]}|+{pos[2]}|{neg[0].removeprefix('rpeval/')}|{neg[1]}|{neg[2]}|{pos[3] and neg[3]}|{pos[4]==neg[4]}|")
assert total==10
