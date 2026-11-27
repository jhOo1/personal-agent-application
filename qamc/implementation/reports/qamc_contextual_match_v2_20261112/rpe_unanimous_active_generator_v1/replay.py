"""Evaluate the fixed unanimity policy against the deployed archived endpoint."""
from pathlib import Path
from collections import Counter, defaultdict
import json
from qamc_rpeval_terminal_judge_sensitivity import inspect

BASE=Path(__file__).resolve().parents[1]
def read(p):
    return json.loads(p.read_text())

def firsts(rows):
    if not rows:
        return []
    assert len({r["memory_id"] for r in rows})==len(rows)
    pairs=[(r["mle_order"],r["ipe_order"]) for r in rows]
    assert all(sorted(order)==list("ABC") for pair in pairs for order in pair)
    return [(a[0],b[0]) for a,b in pairs]

def run():
    results=read(BASE/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
    index={(r["uid"],r["method"]):r for r in results}
    endpoints=read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    # Derive all switches before consulting any grades.
    switches={}
    for r in endpoints:
        if r["old_route"]!="REUSE_RP":
            continue
        rp=index[r["uid"],"RPR_PAPER_FULL"]
        ranks=rp.get("aggregation")
        pairs=firsts(ranks)
        if pairs:
            assert [p["memory_id"] for p in ranks]==[m["memory_id"] for m in rp["view"]["source_evidence"]]
        switches[r["uid"]]=bool(pairs) and all("A" not in pair for pair in pairs)
    total=defaultdict(lambda:defaultdict(Counter))
    transitions=Counter()
    winning_groups=set()
    for r in endpoints:
        a=r["ipe_c"]
        use=switches.get(r["uid"],False)
        if use:
            o=index[r["uid"],"DES2GEN_FULL"]
            grade=o.get("native_fields") or {}
            b={"grade":grade,"flags":inspect(o,r["labels"])["flags"] if grade.get("match") else None}
        else:
            b=a
        if any(not s["grade"].get("match") or any(s["grade"].get(k) is None for k in ("OPB","UPB","FM")) for s in (a,b)):
            transitions["missing_on_switch" if use else "missing_unswitched"]+=1
            continue
        clean=a["flags"]==[] and b["flags"]==[]
        if use:
            d=b["grade"]["match"]["matched"]-a["grade"]["match"]["matched"]
            transitions["win" if d>0 else "loss" if d<0 else "tie"]+=1
            if clean and d>0:winning_groups.add(r["source_group"])
        for arm,s in (("IPE-C",a),("unanimous",b)):
            g=s["grade"]
            for scope in ["all"]+(["clean"] if clean else [])+(["switched"] if use else []):
                total[scope][arm].update(roots=1,positions=g["match"]["positions"],Match=g["match"]["matched"],**{k:g[k] for k in ("OPB","UPB","FM")})
    return dict(assigned=len(endpoints),active=len(switches),switches=sum(switches.values()),paired=total,transitions=transitions,clean_winning_groups=len(winning_groups))
if __name__=="__main__":print(json.dumps(run(),indent=2))
