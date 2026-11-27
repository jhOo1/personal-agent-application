"""Recover the eleven verified answers and original visible task facts privately."""
import json
from pathlib import Path
import sys
from collections import defaultdict

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent/"external_pool_frontier_v1"))
from replay import candidates, archive, read, sha

opps = read(here/"RESULTS.json")["opportunities"]
methods = {k: set(v["methods"]) | {archive.engine.GATE} for k,v in opps.items() if v["missed_attributes"]}
roots = {r["uid"]:r for r in archive.transfer.development_roots("BenchPreS") if r["uid"].split("/")[-1][:8] in methods}
panel = {u:dict(benchmark="BenchPreS") for u in roots}
texts = defaultdict(dict)
for uid, method, answer, _, _ in candidates(panel):
    short = uid.split("/")[-1][:8]
    if method in methods[short]:
        alias=sha(["case-review",uid,method])[:10]
        texts[short][alias]=answer
assert len(texts)==4 and sum(map(len,texts.values()))==11
packet = {}
for uid,root in roots.items():
    short=uid.split("/")[-1][:8]
    packet[short]=dict(task=root["public_task"],sources=root["original_sources"],answers=texts[short])
# Check the specific enrollment claim against RP's actual actor input as well.
uid, = [u for u in roots if u.endswith("2d6ba4ffaa99ad881bc2")]
row, = [r for r in archive.transfer.archived_answers("BenchPreS", {uid})
        if r["method"] == archive.engine.RP]
assert sha(row["actor_request"]) == row["actor_request_sha256"]
wire = "\n".join(m["content"] for m in row["actor_request"]["messages"])
assert "enrolled in the Harvard Online Leadership Essentials course" in wire
assert "enrolled in an online Small Business Management course" in wire
assert "These completed credentials" in row["answer"]
assert sha(row["answer"]) == sha(texts["2d6ba4ff"][sha(["case-review", uid, archive.engine.RP])[:10]])
out=here.parents[2]/"runs"/here.parent.name/here.name/"private"
out.mkdir(parents=True,exist_ok=True)
encoded=json.dumps(packet,ensure_ascii=False,sort_keys=True,indent=2)
path=out/"FOUR_CASES.json"
if path.exists():
    assert path.read_text()==encoded
else:
    with path.open("x") as f:
        f.write(encoded)
print(json.dumps(dict(tasks=len(packet),answers=sum(map(len,texts.values())),fingerprint=sha(encoded)),indent=2))
