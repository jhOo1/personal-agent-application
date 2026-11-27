"""Place fresh matched generations on the scale of the loss that qualified each task."""
from collections import Counter, defaultdict
from pathlib import Path
import json

here = Path(__file__).resolve().parent
base = here.parent
run = here.parents[2] / "runs" / base.name / here.name / "private"
def read(path):
    return json.loads(path.read_text())

frozen = read(run / "FROZEN.json")["wires"]
fresh = {(r["uid"], r["arm"]):r["score"]["grade"] for r in read(run / "RESULTS.json")["rows"]}
old = {r["uid"]:r for r in read(base / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
formal = {r["uid"]:r for r in read(base / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json") if r["method"]=="DES2GEN_FULL"}
totals = defaultdict(Counter)
records = []
for uid in sorted({u for u, a in fresh}):
    assert frozen[uid+"|full"] == formal[uid]["actor_request_sha256"]
    assert old[uid]["old_route"] == "REUSE_RP"
    assert old[uid]["ipe_c"]["answer_sha256"] == old[uid]["scores"]["RPR_PAPER_FULL"]["answer_sha256"]
    cells = dict(IPE=old[uid]["ipe_c"]["grade"], old_Des=formal[uid]["native_fields"],
                 new_full=fresh[uid,"full"], new_mask=fresh[uid,"masked"])
    assert len({g["match"]["positions"] for g in cells.values()}) == 1
    matches = {k:g["match"]["matched"] for k,g in cells.items()}
    assert matches["old_Des"] < matches["IPE"]
    for k,g in cells.items():
        totals[k].update(Match=matches[k], positions=g["match"]["positions"], OPB=g["OPB"], UPB=g["UPB"], FM=g["FM"])
    records.append(dict(case=uid.split("/",2)[-1], matches=matches,positions=cells["IPE"]["match"]["positions"]))
print(json.dumps(dict(cases=records,totals=totals),indent=2))
