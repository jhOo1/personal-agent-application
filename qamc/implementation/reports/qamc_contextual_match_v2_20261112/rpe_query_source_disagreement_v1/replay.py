import json
from collections import Counter, defaultdict
from pathlib import Path
from policy import veto

root = Path(__file__).resolve().parents[1]
panel = json.loads((root / "counterfactual_rpeval_v41/FROZEN.json").read_text())
assert not panel["independent_confirmation"] and len(panel["roots"]) == 233
archive = {r["uid"]: r for r in json.loads((root / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]}
tables = defaultdict(Counter)
groups = defaultdict(Counter)
cases = []
for meta in panel["roots"]:
    r = archive[meta["uid"]]
    cells = r["scores"]
    if not all(c["grade"].get("match") for c in cells.values()):
        continue
    opened = r["old_route"] == "REUSE_RP"
    base = cells["IPE_C"]
    selected = cells["RPR_PAPER_FULL" if opened else "TASK_ONLY"]
    assert base["answer_sha256"] == selected["answer_sha256"] and base["grade"] == selected["grade"]
    for name in ["IPE_C", "aligned", "rotated"]:
        flip = opened and name != "IPE_C" and veto(meta["public_task"]["query"], meta["original_sources"],
                meta["archived_policy"], rotate=name == "rotated")
        grade = (cells["TASK_ONLY"] if flip else base)["grade"]
        m = grade["match"]
        delta = m["matched"] - base["grade"]["match"]["matched"]
        stratum = "C" if "C" in r["labels"] else "B" if "B" in r["labels"] else "A"
        groups[name][r["source_group"]] += delta
        if flip:
            cases.append((name,meta["uid"],stratum,delta))
        for label in ["all",stratum] + (["no_flags"] if not any(c["flags"] for c in cells.values()) else []):
            tables[name + "/" + label].update(tasks=1, changed=int(flip), matched=m["matched"],
                    positions=m["positions"], exact=int(m["matched"] == m["positions"]),
                    OPB=grade["OPB"], UPB=grade["UPB"], FM=grade["FM"])
assert tables["IPE_C/all"]["tasks"] == 216
summary = {"tables":tables,"groups":{k:dict(wins=sum(x>0 for x in v.values()), losses=sum(x<0 for x in v.values()),
        ties=sum(x==0 for x in v.values())) for k,v in groups.items()}}
if __name__ == "__main__":
    print(json.dumps(summary,indent=2))
