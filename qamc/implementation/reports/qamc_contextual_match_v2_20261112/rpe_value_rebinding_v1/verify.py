"""Verify exact edit inputs, the archived routed draft, and both sources of grades."""
import hashlib
import json
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
out = here.parents[2] / "runs" / here.parent.name / here.name
old = out.parent / "rpe_remaining_roots_deployment_v1/deployment1"
read = lambda p: json.loads(p.read_text())

def records(stage):
    for path in stage.glob("visible/*/record.json"):
        yield path, read(path)

routes = read(old / "ROUTES.json")
drafts, sources = {}, {}
for path,r in records(old/"Actor"):
    uid, arm = r["unit"]["root_id"], r["unit"]["method"]
    if routes[uid]["branch"] == arm:
        drafts[uid] = read(path.with_name("response.json"))["answer"]
    if arm == "RP_FULL":
        raw = json.loads(read(path.with_name("request.json"))["messages"][1]["content"])
        sources[uid] = {k:raw[k] for k in ("query","facts","current_context","source_evidence")}
edits = Counter()
for path,r in records(out/"Edit"):
    uid, arm = r["unit"]["root_id"], r["unit"]["method"]
    payload = json.loads(read(path.with_name("request.json"))["messages"][1]["content"])
    assert payload == {**sources[uid],"draft":drafts[uid]}
    edits[uid,arm] += 1
assert len(edits)==48 and set(edits.values())=={1}
print("48 inputs match their fixed task, evidence, and archived routed draft")
prior_rows = {r["uid"]:r for r in read(old/"RESULTS.json")["rows"]}
run = read(out/"RESULTS.json")
fallbacks = 0
for r in run["rows"]:
    if r["action"] in ("INVALID","KEEP"):
        base=prior_rows[r["uid"]]
        assert r["score"]["grade"]==base["scores"][base["branch"]]["grade"]
        fallbacks+=1
ids=set()
physical=Counter()
for stage in ("Edit","Judge"):
    for path,r in records(out/stage):
        req=read(path.with_name("request.json"))
        digest=hashlib.sha256(json.dumps(req,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        assert digest==r["request_sha256"] and r["automatic_retries"]==0
        if r["status"]=="OK":
            rid=read(path.with_name("response.json"))["id"]
            assert rid not in ids
            ids.add(rid)
        physical[stage,r["request_sha256"],r["status"]]+=1
assert physical==Counter((r["unit"]["stage"],r["request_sha256"],r["status"]) for r in run["ledger"])
print(f"{fallbacks} preserved draft grades; {len(ids)} distinct successful physical response IDs")
