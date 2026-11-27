"""Offline paired summaries on complete, changed and genuinely distinct exposure sets."""
import json
from collections import Counter
from panel import BASE, HERE, read

RUN = BASE.parents[1] / "runs" / BASE.name / HERE.name
ARMS = ("FULL", "RP_K", "PB")

def measures(grade):
    if not grade or not grade.get("match"):
        return None
    m = grade["match"]
    return Counter(matched=m["matched"],positions=m["positions"],OPB=grade["OPB"],
                   UPB=grade["UPB"],FM=grade["FM"],tasks=1)

def report():
    endpoints = {r["uid"]:r for r in read(BASE/"ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
    read_stage = read(RUN/"READ_RESULTS.json")
    out = {"assigned":len(read_stage["rows"]),"draws":{}}
    ledger = read_stage["ledger"].copy()
    for rep in range(2):
        p = RUN/f"DRAW{rep}.json"
        if not p.exists():continue
        draw = read(p)
        if set(draw["selection"])!=set(read_stage["rows"]):
            raise ValueError("Roster drift")
        rows={(x["uid"],x["arm"]):x for x in draw["rows"]}
        results={}
        for subset in ("assigned","changed","PB_differs_from_RP_K","common_with_archive","no_grade_flags"):
            pairs={}
            for uid,sel in draw["selection"].items():
                old=endpoints[uid]["ipe_c"] or {}
                archived=measures(old.get("grade"))
                if sel["status"]=="UNCHANGED":
                    cells={arm:archived for arm in ARMS}
                    flags=old.get("flags")
                elif sel["status"]=="CHANGED":
                    cells={arm:measures(rows[uid,arm]["grade"]) if rows[uid,arm]["status"]=="OK" else None for arm in ARMS}
                    flags=any(rows[uid,arm]["flags"] for arm in ARMS)
                else:
                    continue
                if subset=="changed" and sel["status"]!="CHANGED":continue
                if subset=="PB_differs_from_RP_K" and sel.get("pb")==sel.get("rp"):continue
                if subset=="no_grade_flags" and flags:continue
                if subset=="common_with_archive":cells["ARCHIVE"]=archived
                if all(v is not None for v in cells.values()):pairs[uid]=cells
            keys=(*ARMS,"ARCHIVE") if subset=="common_with_archive" else ARMS
            results[subset]={a:dict(sum((v[a] for v in pairs.values()),Counter())) for a in keys}
            results[subset]["uids"]=sorted(pairs)
        out["draws"][rep]=results
        ledger=read_stage["ledger"]+draw["ledger"]
    out["receipts"]=dict(Counter(r["status"] for r in ledger))
    out["reported_tokens"]=sum((r.get("usage") or {}).get("total_tokens",0) for r in ledger)
    out["unknown_usage"]=sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger)
    return out

if __name__=="__main__":
    print(json.dumps(report(),indent=2))
