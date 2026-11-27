"""Pair pre-existing masking interventions with the earlier strict-subset decision."""
from collections import Counter
import json
from pathlib import Path

here = Path(__file__).resolve().parent
base = here.parent
private = here.parents[2] / "runs" / base.name / "des2gen_suppressed_visibility_v1/private"

def read(path):
    return json.loads(path.read_text())

rows = {r["uid"]: r for r in read(base / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]}
formal = {(r["uid"], r["method"]):r for r in read(base / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")}
scores = {(r["uid"], r["arm"]): r["score"]["grade"] for r in read(private / "RESULTS.json")["rows"]}
wires = read(private / "FROZEN.json")["wires"]
counts = Counter()
totals = {arm: Counter() for arm in ("original_IPE", "original_Des2Gen", "fresh_full", "fresh_masked")}
for uid in sorted({uid for uid, arm in scores}):
    counts["mask_trial_assigned"] += 1
    rp, des = [formal[uid, arm] for arm in ("RPR_PAPER_FULL","DES2GEN_FULL")]
    assert rows[uid]["old_route"] == "REUSE_RP"
    assert wires[uid+"|full"] == des["actor_request_sha256"]
    p, d = [json.loads(r["actor_request"]["messages"][-1]["content"]) for r in (rp,des)]
    assert p["source_evidence"] == d["source_evidence"]
    allowed = {a["memory_id"] for a in p["preference_use_policy"] if a["policy"] != "A"}
    hard = {a["memory_id"] for a in p["preference_use_policy"] if a["policy"] == "C"}
    apply = {a["memory_id"] for a in d["applicability_decisions"] if a["decision"] == "Apply"}
    if not (apply < allowed and hard <= apply):
        continue
    counts["switch_condition"] += 1
    grades = [rows[uid]["ipe_c"]["grade"], des["native_fields"] or {}, scores[uid,"full"], scores[uid,"masked"]]
    valid = [bool(g.get("match")) and all(g.get(k) is not None for k in ("OPB","UPB","FM")) for g in grades]
    counts["in_previous_scored_switch_panel"] += all(valid[:2])
    if not all(valid):
        counts["incomplete"] += 1
        continue
    counts["comparable"] += 1
    for arm, grade in zip(totals, grades):
        m = grade["match"]
        assert m["positions"] == len(rows[uid]["labels"])
        totals[arm].update(Match=m["matched"], positions=m["positions"], **{k:grade[k] for k in ("OPB","UPB","FM")})
    old_delta = grades[1]["match"]["matched"] - grades[0]["match"]["matched"]
    counts["archived_loss" if old_delta < 0 else "archived_win" if old_delta > 0 else "archived_tie"] += 1
    diff = grades[3]["match"]["matched"] - grades[2]["match"]["matched"]
    counts["masked_win" if diff>0 else "masked_loss" if diff<0 else "masked_tie"] += 1
print(json.dumps(dict(counts=counts, totals=totals),indent=2))
