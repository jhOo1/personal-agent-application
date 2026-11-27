"""Post-generation diagnostics. Gold is read only for aggregate evaluation."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

base = Path(__file__).resolve().parent.parent
def load(path):
    return json.loads((base/path).read_text())

rows = load("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
actors = {r["uid"]:r for r in load("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
          if r["method"]=="RPR_PAPER_FULL"}
totals = defaultdict(Counter)
groups = defaultdict(set)
missing = Counter()
for row in rows:
    uid = row["uid"]
    actor = actors[uid]
    wire = actor.get("actor_request")
    if not wire:
        missing["no_actor_wire"] += 1
        continue
    payload = json.loads(wire["messages"][-1]["content"])
    policy = payload["preference_use_policy"]
    assert [v["memory_id"] for v in policy] == [v["memory_id"] for v in payload["source_evidence"]]
    pred = "".join(v["policy"] for v in policy)
    gold = row["labels"]
    assert len(pred) == len(gold) and set(pred+gold) <= set("ABC")
    endpoint = row["scores"].get("RPR_PAPER_FULL") or {}
    match = (endpoint.get("grade") or {}).get("match")
    if not match or not actor.get("answer"):
        missing["no_matched_answer_grade"] += 1
        continue
    assert hashlib.sha256(actor["answer"].encode()).hexdigest() == endpoint["answer_sha256"]
    assert match == actor["native_fields"]["match"] and match["positions"] == len(gold)
    stratum = "contains_C" if "C" in gold else "contains_B_no_C" if "B" in gold else "all_A"
    differs = sum(x!=y for x,y in zip(pred,gold))
    missed = len(gold) - match["matched"]
    for s in ("all",stratum):
        for clean in (["all","unflagged"] if endpoint.get("flags")==[] else ["all"]):
            for quality in ("any","exact" if not differs else "inexact"):
                key = "/".join((s,clean,quality))
                groups[key].add(row["source_group"])
                totals[key].update(tasks=1, positions=len(gold), predicted_correct=len(gold)-differs,
                                   answer_match=match["matched"], missed=missed, exact_answers=int(not missed),
                                   misses_on_correct_predictions_lower=max(0,missed-differs),
                                   misses_on_correct_predictions_upper=min(missed,len(gold)-differs))
for key, values in totals.items():
    values["source_groups"] = len(groups[key])
print(json.dumps(dict(assigned=len(rows),missing=missing,tables=totals),indent=2,sort_keys=True))
