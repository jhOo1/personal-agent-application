"""Count source groups, query identities and C multiplicities in the exact-policy slice."""
import hashlib
import json
from collections import Counter
from pathlib import Path

base = Path(__file__).resolve().parent.parent
def read(name):
    return json.loads((base/name).read_text())
raw = read("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
endpoints = {r["uid"]: r for r in read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
groups, queries, multiplicity = Counter(), Counter(), Counter()
for r in raw:
    if r["method"] != "RPR_PAPER_FULL" or not r.get("actor_request"):
        continue
    old = endpoints[r["uid"]]
    labels = old["labels"] or ""
    endpoint = old["scores"].get("RPR_PAPER_FULL") or {}
    if "C" not in labels or not (endpoint.get("grade") or {}).get("match"):
        continue
    p = json.loads(r["actor_request"]["messages"][-1]["content"])
    if "".join(x["policy"] for x in p["preference_use_policy"]) != labels:
        continue
    assert [x["memory_id"] for x in p["preference_use_policy"]] == [x["memory_id"] for x in p["source_evidence"]]
    assert hashlib.sha256(r["answer"].encode()).hexdigest() == endpoint["answer_sha256"]
    groups[old["source_group"]] += 1
    queries[p["query"]] += 1
    multiplicity[labels.count("C")] += 1
assert sum(multiplicity.values()) == 13
print("Conservative groups:", len(groups), "group sizes:", sorted(groups.values(),reverse=True))
print("Distinct literal queries:",len(queries))
print("Number of authored C positions per task -> tasks:", sorted(multiplicity.items()))
