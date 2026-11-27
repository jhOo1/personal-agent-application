"""Recover trigger identities before attaching author labels and archived outcomes."""
import contextlib
import io
import json
import runpy
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

base = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    previous = runpy.run_path(str(base / "query_specific_reopening_v1/replay.py"))
def digest(wire):
    return sha256(json.dumps(wire, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode()).hexdigest()

def restrict(row):
    uid = row["uid"]
    body = previous["bodies"][uid]
    q = body["query"]
    sim = previous["sim"]
    pool = previous["features"]
    others = {t for g,t in previous["bank"] if g != row["source_group"] and t != q}
    evidence = {s["memory_id"]:previous["grams"](s["text"]) for s in body["source_evidence"]}
    policy = {p["memory_id"]:p["policy"] for p in body["preference_use_policy"]}
    floor = max((sim(pool[q],s) for k,s in evidence.items() if policy[k]=="A"),default=0.)
    ids = [k for k,s in evidence.items() if policy[k]!="A" and sim(pool[q],s)>floor
           and all(sim(pool[q],s)>sim(pool[t],s) for t in others)]
    assert ids
    original = previous["original"][uid]
    wire = deepcopy(original["actor_request"])
    assert digest(wire)==original["actor_request_sha256"]
    partial = dict(body)
    for field in ("source_evidence","preference_use_policy"):
        partial[field] = [s for s in body[field] if s["memory_id"] in ids]
    wire["messages"][-1]["content"] = json.dumps(partial, ensure_ascii=False)
    return ids,list(evidence),digest(wire)

cache = {}
for file in ("ipe_rank_information_v1/RUN_RESULTS.json","source_mask_factorization_v1/RESULTS.json"):
    for r in json.loads((base/file).read_text())["rows"]:
        key = r.get("actor_request_sha256") or r["actor"]["request_sha256"]
        if r["actor_status"]=="OK" and (r.get("score") or {}).get("match"):
            cache.setdefault((r["uid"],key),[]).append(r["score"]["match"]["matched"])

print("# Which sources triggered historical reopening?\n")
print("Complete 18-trigger roster from the frozen rule. A/B/C below are author labels joined after source identification. Last column checks exact restricted Actor request hashes against two scored mask and ranked re-entry archives only. No generation calls. Scores in the middle column are for whole endpoints.\n")
print("|Task|Trigger IDs|Author labels of triggers|IPE-C → full Match|Restricted Match in searched cache|")
print("|---|---|---|---|---|")
for row in previous["panel"]:
    uid=row["uid"]
    if not previous["arms"][uid][1]:
        continue
    ids,order,key=restrict(row)
    assert len(order)==len(row["labels"])
    before,after=[((row["scores"].get(k) or {}).get("grade") or {}).get("match") for k in ("IPE_C","RPR_PAPER_FULL")]
    scores=f"{before['matched']} → {after['matched']} / {before['positions']}" if before and after else "missing pair"
    print("|"+"|".join([uid.split("rpeval/")[-1],",".join(ids),"".join(row["labels"][order.index(k)] for k in ids),scores,", ".join(map(str,sorted(set(cache.get((uid,key),[]))))) or "missing"])+"|")
