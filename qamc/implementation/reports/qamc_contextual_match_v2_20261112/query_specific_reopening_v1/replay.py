"""Compare two predeclared switches using only exposed archives."""
import json
import math
import re
from collections import Counter
from pathlib import Path

base = Path(__file__).resolve().parents[1]
def load(path):
    return json.loads((base / path).read_text())

def grams(text):
    return {word[i:i+2] for word in re.findall(r"[^\W_]+", text.lower())
            for i in range(len(word)-1)}

def sim(a, b):
    return len(a & b) / math.sqrt(len(a)*len(b)) if a and b else 0.

panel = load("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
original = {r["uid"]: r for r in load("rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
            if r["method"] == "RPR_PAPER_FULL" and r.get("actor_request")}
bodies = {uid: json.loads(r["actor_request"]["messages"][-1]["content"]) for uid,r in original.items()}
bank = {(r["source_group"], bodies[r["uid"]]["query"]) for r in panel if r["uid"] in bodies}
features = {q:grams(q) for _,q in bank}
def decide(row):
    wire = bodies.get(row["uid"])
    if wire is None or row["old_route"] not in ("REUSE_DRAFT","NEW_DRAFT","REUSE_ORIGINAL_TASK_ONLY_STATE"):
        return False,False
    q = wire["query"]
    sources = {s["memory_id"]:grams(s["text"]) for s in wire["source_evidence"]}
    policy = {s["memory_id"]:s["policy"] for s in wire["preference_use_policy"]}
    assert sources.keys() == policy.keys()
    rejected = max((sim(features[q],s) for k,s in sources.items() if policy[k]=="A"),default=0.)
    eligible = [s for k,s in sources.items() if policy[k] in ("B","C") and sim(features[q],s)>rejected]
    others = {q2 for g,q2 in bank if g!=row["source_group"] and q2!=q}
    return bool(eligible), any(all(sim(features[q],s)>sim(features[q2],s) for q2 in others) for s in eligible)

arms = {r["uid"]:decide(r) for r in panel}
print("# Frozen cross-query reopening replay\n")
print(f"{len(panel)} exposed tasks, {len(bodies)} available RP wires in archive, {len(features)} distinct comparison queries. Original score contracts and missing grades retained.\n")
print("|Policy|Triggered / paired triggers|Trigger roots (paired)|All-A paired triggers|Wins/losses/ties on paired triggers|Common tasks|Match|OPB|UPB|FM|")
print("|---|---:|---:|---:|---|---:|---:|---:|---:|---:|")
for index,name in enumerate(("IPE-C","Within task","Across queries")):
    counts=Counter()
    roots=set()
    for r in panel:
        gates=arms[r["uid"]]
        use=index>0 and gates[index-1]
        counts["trigger"]+=use
        def grade(k):
            return (r["scores"].get(k) or {}).get("grade") or {}
        old,full=grade("IPE_C"),grade("RPR_PAPER_FULL")
        if not(old.get("match") and full.get("match")):
            continue
        assert old["match"]["positions"]==full["match"]["positions"]
        new=full if use else old
        if use:
            roots.add(r["source_group"])
            counts["paired"]+=1
            counts["all_A"]+=set(r["labels"])=={"A"}
            diff=new["match"]["matched"]-old["match"]["matched"]
            counts["win" if diff>0 else "loss" if diff<0 else "tie"]+=1
        counts["tasks"]+=1
        counts["n"]+=new["match"]["positions"]
        counts["m"]+=new["match"]["matched"]
        for field in ("OPB","UPB","FM"):
            assert isinstance(new[field],int)
            counts[field]+=new[field]
    c=counts
    print(f"|{name}|{c['trigger']} / {c['paired']}|{len(roots)}|{c['all_A']}|{c['win']}/{c['loss']}/{c['tie']}|{c['tasks']}|{c['m']}/{c['n']}|{c['OPB']}|{c['UPB']}|{c['FM']}|")
