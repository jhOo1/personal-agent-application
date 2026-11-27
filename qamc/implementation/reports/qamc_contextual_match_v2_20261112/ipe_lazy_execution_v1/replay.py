"""Count generation requests for a cold deployment that defers MLE until needed."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from policy import history_on

base = Path(__file__).resolve().parent.parent
def read(path):
    return json.loads((base/path).read_text())

formal = {r["uid"]:r for r in read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json") if r["method"]=="RPR_PAPER_FULL"}
policy = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
tables = defaultdict(Counter)
for r in policy:
    if r["old_route"] == "ARCHIVED_ESTIMATE_OR_ACTOR_UNAVAILABLE":
        tables["allocation"]["route_unknown"] += 1
        continue
    rankings = formal[r["uid"]]["aggregation"]
    on = history_on([a["ipe_order"] for a in rankings])
    assert on == (r["old_route"] == "REUSE_RP")
    selected = r["scores"]["IPE_C"]
    endpoint = r["scores"]["RPR_PAPER_FULL" if on else "TASK_ONLY"]
    if selected["answer_sha256"]:
        assert selected["answer_sha256"] == endpoint["answer_sha256"]
    for panel in ["known_route"] + (["three_scored_endpoints"] if all(c["grade"].get("match") for c in r["scores"].values()) else []):
        c = tables[panel]
        c["history_on" if on else "history_off"] += 1
        c["lazy_nominal_calls"] += 2 + int(on)
        c["rp_nominal_calls"] += 3
        if panel == "three_scored_endpoints":
            for name, cell in r["scores"].items():
                c[name+"_Match"] += cell["grade"]["match"]["matched"]
            c["positions"] += selected["grade"]["match"]["positions"]
print(json.dumps(tables,indent=2))
