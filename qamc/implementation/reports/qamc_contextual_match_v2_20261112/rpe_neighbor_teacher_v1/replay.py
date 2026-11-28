"""Freeze switches on public query/features first; join grades only for evaluation."""
from collections import defaultdict, Counter
from pathlib import Path
from statistics import mean
import json

base = Path(__file__).resolve().parent.parent
def read(path):
    return json.loads((base/path).read_text())

def normalize(s):
    return "".join(s.lower().split())

public = {r["uid"]: normalize(r["public_task"]["query"])
          for r in read("counterfactual_rpeval_v41/FROZEN.json")["roots"]}
archive = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
on = "REUSE_RP"
off = {"REUSE_ORIGINAL_TASK_ONLY_STATE", "REUSE_DRAFT", "NEW_DRAFT"}
teachers = [(public[r["uid"]],r["source_group"],r["old_route"]==on)
            for r in archive if r["uid"] in public and r["old_route"] in off|{on}]
grams = {q:set(zip(q,q[1:])) for q in public.values()}
assert all(grams.values())
def transfer(query, group):
    donors = defaultdict(lambda:defaultdict(list))
    for q, g, bit in teachers:
        if q != query and group != g:
            donors[q][g].append(bit)
    def similarity(q):
        return len(grams[q]&grams[query])/len(grams[q]|grams[query])
    nearest = min(donors,key=lambda q:(-similarity(q),q))
    return similarity(nearest)>0 and mean(mean(bits) for bits in donors[nearest].values())>.5

decisions = {r["uid"]:transfer(public[r["uid"]],r["source_group"])
             for r in archive if r["uid"] in public}
summary = defaultdict(Counter)
for r in archive:
    if r["uid"] not in decisions or r["old_route"] not in off|{on}:
        continue
    arms = [r["scores"].get(k) or {} for k in ("TASK_ONLY","RPR_PAPER_FULL","IPE_C")]
    if not all((a.get("grade") or {}).get("match") for a in arms):
        continue
    teacher = r["old_route"]==on
    assert arms[int(teacher)]["answer_sha256"] == arms[2]["answer_sha256"]
    n = len(r["labels"])
    assert all(a["grade"]["match"]["positions"]==n for a in arms)
    label = "C present" if "C" in r["labels"] else "B without C" if "B" in r["labels"] else "all A"
    scopes = ["common", label] + (["flag-free"] if all(not a["flags"] for a in arms) else [])
    for scope in scopes:
        for name,bit in (("transfer",decisions[r["uid"]]),("IPE-C",teacher),("empty",False),("full",True)):
            grade = arms[int(bit)]["grade"]
            match = grade["match"]["matched"]
            summary[scope,name].update(n=1,on=int(bit),positions=n,match=match,exact=int(match==n),
                                       **{k:grade[k] for k in ("OPB","UPB","FM")})
print(f"Exposed roster {len(public)}; eligible route decisions for donors {len(teachers)}. No model calls.\n")
print("|Panel|Policy|Tasks|Open|Match / positions|Exact|OPB|UPB|FM|\n|---|---|---:|---:|---:|---:|---:|---:|---:|")
for (scope,name),s in summary.items():
    print(f"|{scope}|{name}|{s['n']}|{s['on']}|{s['match']}/{s['positions']}|{s['exact']}|{s['OPB']}|{s['UPB']}|{s['FM']}|")
