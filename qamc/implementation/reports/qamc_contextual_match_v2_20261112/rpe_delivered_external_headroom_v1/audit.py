"""Offline inventory of alternate final answers when the deployed IPE-C path used RP."""
import json
from collections import Counter, defaultdict
from pathlib import Path
import qamc_rpeval_formal_multi_run as formal
from qamc.common import sha
from qamc_rpeval_terminal_judge_sensitivity import inspect

BASE = Path(__file__).resolve().parents[1]
def read(p):
    return json.loads(p.read_text())

def main():
    endpoints = read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    results = {(r["uid"],r["method"]):r for r in read(BASE/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")}
    totals = defaultdict(Counter)
    examples = []
    groups = defaultdict(set)
    for e in endpoints:
        uid, labels = e["uid"],e["labels"]
        if e["old_route"]!="REUSE_RP" or not any(l in "BC" for l in labels):
            continue
        arm = results[uid,"RPR_PAPER_FULL"]
        if not arm.get("answer") or not e["ipe_c"].get("grade",{}).get("match"):
            continue
        assert sha(arm["answer"])==e["ipe_c"]["answer_sha256"]
        assert sha(arm["actor_request"])==arm["actor_request_sha256"]
        evidence=json.loads(arm["actor_request"]["messages"][-1]["content"])["source_evidence"]
        task=formal.task_for({"uid":uid})
        assert evidence==[{"memory_id":m.memory_id,"text":m.text} for m in task.memories] and len(evidence)==len(labels)
        base=arm["native_fields"]
        assert base["match"]==e["ipe_c"]["grade"]["match"]
        for method in ("DES2GEN_FULL","MEMADAPTER_FULL"):
            other=results[uid,method]
            alt=other.get("native_fields") or {}
            t=totals[method]
            t["delivered"]+=1
            if not alt.get("match") or not all(k in f for f in (base,alt) for k in ("OPB","UPB","FM")):
                continue
            assert alt["match"]["positions"]==len(labels)
            t["common"]+=1
            if inspect(other,labels)["flags"] or e["ipe_c"]["flags"]!=[]:
                continue
            t["clean"]+=1
            diff=alt["match"]["matched"]-base["match"]["matched"]
            t["net_match"]+=diff
            t["positions"]+=len(labels)
            if diff>0 and all(alt[k]<=base[k] for k in ("OPB","UPB","FM")):
                t["protected_wins"]+=1
                t["protected_gain"]+=diff
                groups[method].add(e["source_group"])
                examples.append((uid,method,diff,base["UPB"],alt["UPB"]))
    for m,g in groups.items():totals[m]["winning_groups"]=len(g)
    print(json.dumps(dict(summary=totals, protected_pairs=examples),indent=2))
if __name__=="__main__":main()
