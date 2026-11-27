"""Post-freeze diagnostic of the two saved endpoints. Never used by the selector."""
from collections import Counter
import json

from score import BASE, OUT, RUNS, read


def report():
    labels = read(OUT/"FROZEN.json")["assignments"]
    rpe = {r["uid"]:r for r in read(BASE/"selective_path_frontier_v1/RESULTS.json")["rows"]}
    persist = {}
    for path in (RUNS/"persist_exposure_fr3_v1").glob("*_SETTLED.json"):
        for r in read(path)["rows"]:
            key = (r["uid"],r["repeat"])
            if key in persist: raise ValueError("Repeated archived deployment")
            persist[key] = r["methods"]
    result = {}
    for uid,category in labels.items():
        c = result.setdefault(category,Counter())
        c["assigned"] += 1
        if uid in rpe:
            row=rpe[uid]
            full=row["cells"]["RPR_PAPER_FULL"]["matched"]
            empty=row["cells"]["TASK_ONLY"]["matched"]
            base=row["cells"][row["base"]]["matched"]
            c.update(full=full,empty=empty,ipe_c=base,oracle=max(full,empty),positions=row["positions"])
            c["full_better" if full>empty else "empty_better" if empty>full else "tied"]+=1
            if not any(row["cells"][m]["flags"] for m in ("RPR_PAPER_FULL","TASK_ONLY")):
                c["no_known_flags_tasks"]+=1
                c["no_known_flags_positions"]+=row["positions"]
                c["no_known_flags_headroom_over_ipe_c"]+=max(full,empty)-base
            continue
        # A single choice must serve the entire sequence of deployments.
        def passed(method):
            utility=category=="beneficial_memory_usage"
            vals=[(persist[uid,i][method]["score"] or {}).get("rating") for i in range(1,2 if utility else 4)]
            if utility: return vals[0]==3 if vals[0] is not None else None
            if any(v is not None and v>=3 for v in vals):return False
            return None if None in vals else True
        full,empty=passed("FULL"),passed("EMPTY")
        if full is None or empty is None:
            c["incomplete_endpoint_pair"]+=1
        else:
            c["paired"]+=1
            c["full_better" if full>empty else "empty_better" if empty>full else "tied"]+=1
            c["full_pass"]+=full
            c["empty_pass"]+=empty
        lower=max(full is True,empty is True)
        upper=max(full is not False,empty is not False)
        c["oracle_pass_lower"]+=lower
        c["oracle_pass_upper"]+=upper
        for ref in ("SELECTED","RUBRIC"):
            p=passed(ref)
            # Cannot transfer an unknown outcome to a different arm.
            if p is not None:
                c[ref+"_known"]+=1
                c[ref+"_pass"]+=p
                c[ref+"_oracle_gain_lower"]+=int(lower)-int(p)
                c[ref+"_oracle_gain_upper"]+=int(upper)-int(p)
    assert len(labels)==36 and len(result)==6
    return result


if __name__=="__main__":print(json.dumps(report(),indent=2,sort_keys=True))
