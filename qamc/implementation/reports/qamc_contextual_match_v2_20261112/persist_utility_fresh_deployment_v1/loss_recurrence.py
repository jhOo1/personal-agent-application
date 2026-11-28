"""Check earlier deployment and fixed-answer judge receipts for all fresh strict losses."""
import json
from pathlib import Path
import subprocess

here = Path(__file__).resolve().parent
runs = here.parents[2] / "runs" / here.parent.name
def read(p):
    return json.loads(p.read_text())

fresh = {(r["uid"],r["arm"]): r for r in read(runs/here.name/"private/SETTLED.json")["rows"]}
prior = {r["uid"]: r for r in read(runs/"persist_exposure_fr3_v1/RESULTS.json")["rows"]
         if r["track"] == "beneficial_memory_usage"}
old_qwen = {r["uid"]: r for r in read(runs/"persist_selected_crossjudge_fr3_v1/private/RESULTS.json")["rows"]
            if r["track"] == "beneficial_memory_usage" and r["arm"] == "SELECTED"}
rows = []
for uid in sorted(prior):
    selected, full = [fresh[uid,arm] for arm in ("SELECTED", "FULL")]
    if selected["Qwen"] not in (1,2) or full["Qwen"] != 3:
        continue
    snapshot = json.loads(subprocess.check_output(["bash", str(here/"inspect.sh"),uid.split("/")[-1]]))
    arms = {}
    for arm in ("SELECTED","FULL"):
        new = snapshot["arms"][arm]
        old = prior[uid]["methods"][arm]
        grade = old["score"]
        arms[arm] = dict(same_request=old["actor"]["request_sha256"] == new["wire"]
                         if old["actor"] else None,
                         prior_status=old["status"],prior_gpt=grade["rating"] if grade else None,
                         same_answer=old["actor"]["answer"]==new["answer"]
                         if old["actor"] and old["actor"].get("status")=="OK" else None)
    rows.append(dict(case=uid.rsplit("/",1)[1][:8],arms=arms,prior_selected_qwen=old_qwen[uid]["qwen"],
                     prior_selected_count=prior[uid]["exposure"]["count"],
                     fresh_selected_count=len(snapshot["selected_sources"])))
assert len(rows)==3
print(json.dumps(rows,indent=2))
