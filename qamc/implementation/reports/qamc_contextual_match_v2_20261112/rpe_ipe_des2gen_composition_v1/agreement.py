"""Test a conservative switch using only the two pre-generation policies."""
from collections import Counter, defaultdict
from pathlib import Path
import json

base = Path(__file__).resolve().parent.parent
rows = json.loads((base / "ipe_c_two_endpoint_completion_v1/RESULTS.json").read_text())["rows"]
formal = json.loads((base / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json").read_text())
lookup = {(r["uid"], r["method"]): r for r in formal}

def policy_sets(rp, des):
    r, d = (json.loads(x["actor_request"]["messages"][-1]["content"]) for x in (rp, des))
    for field in ("query", "current_context", "facts", "source_evidence"):
        assert r[field] == d[field]
    ids = [m["memory_id"] for m in r["source_evidence"]]
    a, b = r["preference_use_policy"], d["applicability_decisions"]
    assert [x["memory_id"] for x in a] == [x["memory_id"] for x in b] == ids
    assert all(x["policy"] in ("A", "B", "C") for x in a)
    assert all(x["decision"] in ("Apply", "Suppress") for x in b)
    return ({x["memory_id"] for x in a if x["policy"] != "A"},
            {x["memory_id"] for x in a if x["policy"] == "C"},
            {x["memory_id"] for x in b if x["decision"] == "Apply"})

counts = defaultdict(Counter)
by_root = Counter()
for row in rows:
    if row["old_route"] != "REUSE_RP":
        continue
    uid = row["uid"]
    rp, des = (lookup[uid, m] for m in ("RPR_PAPER_FULL", "DES2GEN_FULL"))
    if not all(x.get("actor_request") for x in (rp, des)):
        counts["availability"]["missing_policy"] += 1
        continue
    allowed, hard, proposed = policy_sets(rp, des)
    switch = proposed < allowed and hard <= proposed
    first, second = row["scores"]["IPE_C"]["grade"], des.get("native_fields") or {}
    if any(not g.get("match") or any(g.get(k) is None for k in ("OPB","UPB","FM")) for g in (first, second)):
        counts["availability"]["missing_grade"] += 1
        continue
    assert first["match"]["positions"] == second["match"]["positions"]
    c = counts["switch" if switch else "keep"]
    c["tasks"] += 1
    c["positions"] += first["match"]["positions"]
    for name,g in (("IPE",first),("Des2Gen",second)):
        c[name+"_Match"] += g["match"]["matched"]
        for k in ("OPB","UPB","FM"):
            c[name+"_"+k] += g[k]
    if switch:
        by_root[row["source_group"]] += second["match"]["matched"]-first["match"]["matched"]
print(json.dumps({"history_on": counts, "switch_group_net": Counter("win" if v>0 else "loss" if v<0 else "tie" for v in by_root.values())},indent=2))
