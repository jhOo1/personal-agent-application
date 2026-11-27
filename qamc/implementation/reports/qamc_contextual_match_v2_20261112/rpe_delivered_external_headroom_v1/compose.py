"""Use the fixed reader decision with one generator per active branch."""
from collections import Counter, defaultdict
import json
from audit import BASE, read, inspect

def run():
    full={r["uid"]:r for r in read(BASE/"rpeval_formal_multi_coverage_v1/RESULT_ROWS.json") if r["method"]=="DES2GEN_FULL"}
    rows=read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    tables=defaultdict(lambda:defaultdict(Counter))
    bounds=Counter()
    for r in rows:
        if not r["labels"]:
            assert not r["ipe_c"]["grade"].get("match")
            continue
        a=r["ipe_c"]
        o=full[r["uid"]]
        b={"grade":o.get("native_fields") or {},"flags":None}
        if b["grade"].get("match"): b["flags"]=inspect(o,r["labels"])["flags"]
        path=r["old_route"]
        c=b if path=="REUSE_RP" else a if path in ("REUSE_ORIGINAL_TASK_ONLY_STATE","REUSE_DRAFT","NEW_DRAFT") else {"grade":{}}
        if a["grade"].get("match"):
            m=a["grade"]["match"]
            alt=c["grade"].get("match")
            bounds.update(scored_reference=1,low=(alt["matched"] if alt else 0)-m["matched"],
                          high=(alt["matched"] if alt else m["positions"])-m["matched"],missing=int(not alt))
        cat="contains_C" if "C" in r["labels"] else "B_only" if "B" in r["labels"] else "all_A"
        for scope in ("all",cat):
            for name,arms in (("pair",{"IPE-C":a,"composition":c}),("three",{"IPE-C":a,"composition":c,"always_Des2Gen":b})):
                if any(not s["grade"].get("match") or any(s["grade"].get(k) is None for k in ("OPB","UPB","FM")) for s in arms.values()):continue
                for flag in ("raw","unflagged"):
                    if flag=="unflagged" and any(s["flags"]!=[] for s in arms.values()):continue
                    for method,s in arms.items():
                        g=s["grade"];m=g["match"]
                        assert m["positions"]==len(r["labels"])
                        tables[scope+"/"+name+"/"+flag][method].update(tasks=1,Match=m["matched"],positions=m["positions"],OPB=g["OPB"],UPB=g["UPB"],FM=g["FM"])
    return {"assigned":len(rows),"bounds":bounds,"tables":tables}
if __name__=="__main__":print(json.dumps(run(),indent=2))
