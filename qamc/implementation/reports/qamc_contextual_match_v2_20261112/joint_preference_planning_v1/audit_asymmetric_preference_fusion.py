"""Test non-compensatory fusion on archived RP-Reasoner evidence."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_outcome_contract as archive


ORIGINAL = "PAPER_FUSION"
CONTEXT_ONLY = "MLE_ONLY"
CONTEXT_FIRST = "CONTEXT_FIRST"
METHODS = (ORIGINAL, CONTEXT_ONLY, CONTEXT_FIRST)


def fuse(mle, ipe):
    if sorted(mle) != list("ABC") or sorted(ipe) != list("ABC"):
        raise ValueError("Expected rankings of all three valid policy levels")
    if mle[0] == "A":
        return "A"
    if ipe[0] == "C" and mle.index("C") < mle.index("A"):
        return "C"
    return "B"


def native_controls(directory):
    # Only read the exact set of exposed, verified estimator results.
    index_path = directory / "RPR_RANK_FUSION_AUDIT_300.json"
    reference = archive.read(index_path)
    refs = {row["uid"]: row for row in reference["rows"]}
    results = archive.read(directory / "RESULT_ROWS.json")
    roots = {row["uid"]: row for row in results
             if row["method"] == archive.RP and row["uid"] in refs}
    if len(roots) != reference["verified_roots"] or roots.keys() != refs.keys():
        raise ValueError("Verified exposed estimator roster changed")
    return index_path, refs, roots


def audit():
    directory = archive.replay.prior.formal.OUT
    index_path, refs, roots = native_controls(directory)
    counts, groups, cells = defaultdict(Counter), defaultdict(Counter), []
    for uid, row in roots.items():
        ref = refs[uid]
        wire = row["actor_request"]
        actual = json.loads(wire["messages"][1]["content"])
        policies = actual["preference_use_policy"]
        expected = ref["policies"][ORIGINAL]
        if (sha(wire) != expected["actor_request_sha256"]
                or sha(wire) != row["actor_request_sha256"]
                or "".join(item["policy"] for item in policies) != expected["policy"]):
            raise ValueError("Exact original Actor condition changed")
        observed = {arm: [] for arm in METHODS}
        for truth, item, ranked in zip(ref["author_labels"], policies, row["aggregation"], strict=True):
            if (item["memory_id"], item["policy"]) != (ranked["memory_id"], ranked["policy"]):
                raise ValueError("Old policy and estimator orders are misaligned")
            mle, ipe, original = (ranked[field] for field in ("mle_order", "ipe_order", "policy"))
            proposed = fuse(mle, ipe)
            for arm, policy in zip(METHODS, (original, mle[0], proposed), strict=True):
                observed[arm].append({"memory_id": item["memory_id"], "policy": policy})
                counts[arm].update({"positions": 1, "exact": int(policy == truth),
                                    f"label_{truth}": 1, f"{truth}_retained": int(policy != "A"),
                                    f"{truth}_exact": int(policy == truth)})
            groups[ref["source_group"]].update({"positions": 1, "exact_gain": int(proposed == truth) - int(original == truth),
                                                "A_releases_avoided": int(truth == "A" and original != "A")
                                                - int(truth == "A" and proposed != "A")})
        for arm in METHODS:
            counts[arm]["unchanged_Actor_requests"] += observed[arm] == policies
        cells.append({"uid": uid, "source_group": ref["source_group"], "policy": observed[CONTEXT_FIRST],
                      "original_actor_sha256": sha(wire), "changed_wire": observed[CONTEXT_FIRST] != policies})

    old, new = (counts[arm] for arm in (ORIGINAL, CONTEXT_FIRST))
    checks = {"A_release_reduced_at_least_3pp": old["A_retained"] - new["A_retained"] >= .03 * old["label_A"],
              "B_retention_at_least_original": new["B_retained"] >= old["B_retained"],
              "B_exact_at_least_original": new["B_exact"] >= old["B_exact"],
              "C_retention_loss_at_most_one": new["C_retained"] >= old["C_retained"] - 1,
              "C_exact_at_least_original": new["C_exact"] >= old["C_exact"],
              "net_exact_gain": new["exact"] > old["exact"]}
    return {"positions": new["positions"], "roots": len(cells), "physical_requests": 0,
            "index_sha256": sha(index_path.read_bytes()), "methods": counts, "groups": groups,
            "cells": cells, "screen": checks, "passed": all(checks.values())}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
