"""Measure whether disagreement-only exposure differs from equal-size RP ranking."""
from collections import Counter
import json
from pathlib import Path

base = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads((base/path).read_text())

panel = read("ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
archive = "rpeval_formal_multi_coverage_v1/"
pred = {r["uid"]: r["policies"] for r in read(archive+"RPR_RANK_FUSION_AUDIT_300.json")["rows"]}
rp = {r["uid"]: r for r in read(archive+"RESULT_ROWS.json") if r["method"] == "RPR_PAPER_FULL"}
old = {r["uid"] for r in read("source_local_reentry_v1/RESULTS.json")["rows"]}
totals = Counter()
labels_by_arm = {"disagreement":Counter(), "same_count":Counter()}
different = {arm:Counter() for arm in labels_by_arm}
roots = set()
for row in panel:
    if not all(v["grade"].get("match") for v in row["scores"].values()):
        continue
    totals["paired_panel"] += 1
    uid = row["uid"]
    p = pred[uid]
    ipe, mle, fused = [p[k]["policy"] for k in ("IPE_ONLY","MLE_ONLY","PAPER_FUSION")]
    assert (row["old_route"] == "REUSE_RP") == ("C" in ipe)
    assert p["PAPER_FUSION"]["actor_request_sha256"] == rp[uid]["actor_request_sha256"]
    assert len(ipe) == len(mle) == len(fused) == len(row["labels"])
    if "C" in ipe:
        continue
    selected = [i for i,(a,b) in enumerate(zip(ipe,mle)) if (a,b)==("B","C")]
    if not selected:
        continue
    ordered = sorted(range(len(fused)),key=lambda i:"CBA".index(fused[i]))
    control = sorted(ordered[:len(selected)])
    totals["triggered"] += 1
    totals["prior_local_reentry_uid_overlap"] += uid in old
    changed = selected != control
    totals["different_from_equal_size_rp"] += changed
    if changed:
        roots.add(row["source_group"])
    # Read label values only after both exposure decisions are fixed.
    for label in ("B","C"):
        added = sum(row["labels"][i] == label for i in set(selected)-set(control))
        lost = sum(row["labels"][i] == label for i in set(control)-set(selected))
        totals[label+"_new_positions"] += added
        totals[label+"_lost_positions"] += lost
        totals[label+"_tasks_with_net_increase"] += added > lost
        totals[label+"_tasks_with_net_decrease"] += added < lost
    for method, indices in (("disagreement",selected),("same_count",control)):
        values = [row["labels"][i] for i in indices]
        labels_by_arm[method].update(values)
        if changed:
            different[method].update(values)
totals["different_source_groups"] = len(roots)
assert totals["triggered"] == 24
print(json.dumps(dict(tasks=totals, source_positions=labels_by_arm,
                      source_positions_on_different_inputs=different),indent=2,sort_keys=True))
