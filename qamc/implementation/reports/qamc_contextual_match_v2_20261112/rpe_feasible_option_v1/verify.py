"""Verify saved Actor and judge envelopes, hashes, and ledger accounting offline."""
from copy import deepcopy
from pathlib import Path
import json
from qamc.common import sha
here=Path(__file__).resolve().parent
run=here.parents[2]/"runs"/here.parent.name/here.name
def read(p):return json.loads(p.read_text())
pin=read(run/"private/FROZEN.json"); settled=read(run/"private/SETTLED.json")
roots={r["uid"]:r for r in read(here.parent/"counterfactual_rpeval_v41/FROZEN.json")["roots"]}
count=tokens=0
for stage in ("FeasibleActor","FeasibleGrade"):
    manifest=read(run/"private"/(stage+"_MANIFEST.json"))
    expected={sha(unit["request"]) for unit in manifest["units"]}
    found=set()
    for path in (run/stage/"visible").glob("*/record.json"):
        r=read(path);w=read(path.with_name("request.json"))
        assert sha(w)==r["request_sha256"] and r["automatic_retries"]==0
        found.add(sha(w));count+=1;tokens+=(r["usage"] or {}).get("total_tokens",0)
        if stage=="FeasibleActor":
            u=r["unit"]["root_id"]; original=roots[u]["archived_actor_request"]; restored=deepcopy(w)
            assert w["messages"][0]["content"].startswith(original["messages"][0]["content"]+"\n")
            restored["messages"][0]=original["messages"][0]
            assert restored==original and u in pin["panel"]
        else:assert w["model"]=="gpt-4.1"
    assert expected==found
assert count==settled["requests"] and tokens==settled["reported_tokens"]
print("Actor payload invariance, receipt identity, model alias and token totals verified.")
