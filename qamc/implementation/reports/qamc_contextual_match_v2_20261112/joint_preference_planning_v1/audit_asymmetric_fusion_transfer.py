"""Verify the effect of the frozen fusion rule on archived public transfer inputs."""
from collections import Counter
import json

from qamc.common import sha

from audit_asymmetric_preference_fusion import fuse
from transfer_edit import PANELS, RP, archived_answers, context
from transfer_execution import development_roots


def audit(benchmark):
    roots = {row["uid"]: row for row in development_roots(benchmark)}
    cases, protocol, controls = context(benchmark)
    if roots.keys() != cases.keys():
        raise ValueError("Only the frozen development transfer cohorts are allowed")
    rp_rows = {row["uid"]: row for row in archived_answers(benchmark, roots) if row["method"] == RP
               and row.get("actor_request") and sha(row["actor_request"]) == roots[row["uid"]]["archived_actor_sha256"]}
    if rp_rows.keys() != roots.keys():
        raise ValueError("Missing exact RP answers with estimator outputs")
    transitions, items = Counter(), []
    for uid, root in roots.items():
        ranks = rp_rows[uid]["aggregation"]
        policy = root["archived_policy"]
        if [(r["memory_id"], r["policy"]) for r in policy] != [(r["memory_id"], r["policy"]) for r in ranks]:
            raise ValueError("Predictor rows and exact Actor input disagree")
        before = [row["policy"] for row in policy]
        after = [fuse(r["mle_order"], r["ipe_order"]) for r in ranks]
        transitions.update(f"{left}/{right}" for left, right in zip(before, after, strict=True))
        items.append({"uid": uid, "before": before, "after": after, "original_sha256": root["archived_actor_sha256"],
                      "changed": before != after})
    changed = sum(r["changed"] for r in items)
    grades = Counter(row["method"] for row in controls if row["score"] is not None)
    return {"assigned": len(roots), "changed": changed, "unchanged": len(roots) - changed,
            "grade_model": protocol["model"], "existing_strict_grades": grades, "transitions": transitions,
            "max_matched_Actor_requests": 2 * changed,
            "max_matched_Judge_requests": 2 * changed * (6 if benchmark == "BenchPreS" else 1),
            "rows": items}


if __name__ == "__main__":
    print(json.dumps({"physical_requests": 0, "panels": {name: audit(name) for name in PANELS}},
                     ensure_ascii=False, indent=2))
