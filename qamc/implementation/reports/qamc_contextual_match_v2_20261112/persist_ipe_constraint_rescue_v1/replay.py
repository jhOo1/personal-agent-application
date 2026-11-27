"""Zero-call replay; keep root outcomes and differences private."""
import json
from pathlib import Path
from collections import defaultdict, Counter
from qamc.common import sha

BASE = Path(__file__).resolve().parents[1]
ARCHIVE = BASE.parents[1] / "runs" / BASE.name
def read(path):
    return json.loads(path.read_text())

def main():
    cases = {r["uid"]:r for r in read(BASE / "persist_author_controls_v2/PLAN.json")["cases"]}
    rp = {r["uid"]:r for r in read(BASE / "paper_baseline_validation_156_v1/RESULT_ROWS.json")
          if r["method"]=="RPR_PAPER_FULL"}
    tracks = defaultdict(dict)
    changes = defaultdict(Counter)
    verified = set()
    for file in sorted((ARCHIVE/"persist_exposure_fr3_v1").glob("*_SETTLED.json")):
        for row in read(file)["rows"]:
            uid, track = row["uid"], row["track"]
            case = cases[uid]
            assert case["role"]=="DEV" and case["category"]==track
            record = rp.get(uid,{})
            ranks = record.get("aggregation")
            orders = None
            if ranks:
                view = record["view"]
                evidence = view["source_evidence"]
                assert sha(dict(query=view["query"],memories=[s["text"] for s in evidence]))==case["public_sha256"]
                assert [s["memory_id"] for s in ranks]==[s["memory_id"] for s in evidence]
                assert all(sorted(s["ipe_order"])==list("ABC") for s in ranks)
                orders = [s["ipe_order"][0] for s in ranks]
                verified.add(uid)
            group = (row["exposure"] or {}).get("group_endpoint")
            changes[track]["original_"+str(group)]+=1
            paths = {m:m for m in ("SELECTED","FULL","RUBRIC")}
            paths["IPE-C"] = ("FULL" if "C" in orders else "EMPTY") if orders else None
            for name,signal in (("rescue_C","C"),("rescue_BC","BC")):
                if group=="FULL":
                    paths[name]="SELECTED"
                elif group=="EMPTY" and orders:
                    reopen=any(label in signal for label in orders)
                    paths[name]="FULL" if reopen else "SELECTED"
                    changes[track][name+"_reopens"]+=int(reopen)
                else:
                    paths[name]=None
            ratings={k:(row["methods"].get(m) or {}).get("score") for k,m in paths.items()}
            draws=tracks[track].setdefault(uid,{})
            assert row["repeat"] not in draws
            draws[row["repeat"]]={k:v["rating"] if v else None for k,v in ratings.items()}
    totals={}
    for track, roots in tracks.items():
        assigned=defaultdict(Counter)
        pairs=defaultdict(Counter)
        for uid,draws in roots.items():
            bu=track=="beneficial_memory_usage"
            assert set(draws)==({1} if bu else {1,2,3})
            results={}
            for name in draws[1]:
                v=[d[name] for d in draws.values()]
                fail=any(x is not None and (x!=3 if bu else x>=3) for x in v)
                status="fail" if fail else "pass" if None not in v else "unknown"
                assigned[name][status]+=1
                results[name]=status
            for name,status in results.items():
                original=results["SELECTED"]
                pairs[name][original+"->"+status]+=1
        totals[track]={"assigned":assigned,"transitions_from_selected":pairs,"changes":changes[track]}
    assert sum(map(len,tracks.values()))==49
    print(json.dumps(dict(verified_rp_roots=len(verified),tracks=totals),indent=2))
if __name__=="__main__": main()
