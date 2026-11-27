"""Test a conservative switch using only the two pre-generation policies."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import sys

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
label_audit = defaultdict(Counter)
audit_requested = sys.argv[1:] == ["--audit-labels"]
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
        if audit_requested:
            source_ids = [s["memory_id"] for s in json.loads(rp["actor_request"]["messages"][-1]["content"])["source_evidence"]]
            assert source_ids == [f"M{i}" for i in range(len(row["labels"]))]
            authors = dict(zip(source_ids, row["labels"]))
            dropped = Counter(authors[k] for k in allowed - proposed)
            label_audit["newly_suppressed"].update(dropped)
            label_audit["still_apply"].update(authors[k] for k in proposed)
            label_audit["already_ignored"].update(authors[k] for k in set(authors) - allowed)
            group = label_audit["only_A_removed" if not (dropped["B"] or dropped["C"]) else "B_or_C_removed"]
            group["tasks"] += 1
            group["positions"] += len(authors)
            group["Match_delta"] += second["match"]["matched"] - first["match"]["matched"]
            for field in ("OPB", "UPB", "FM"):
                group[field+"_delta"] += second[field] - first[field]
if audit_requested:
    assert sum(sum(label_audit[k].values()) for k in ("newly_suppressed","still_apply","already_ignored")) == counts["switch"]["positions"]
    print(json.dumps(label_audit, indent=2))
else:
    print(json.dumps({"history_on": counts, "switch_group_net": Counter("win" if v>0 else "loss" if v<0 else "tie" for v in by_root.values())},indent=2))
