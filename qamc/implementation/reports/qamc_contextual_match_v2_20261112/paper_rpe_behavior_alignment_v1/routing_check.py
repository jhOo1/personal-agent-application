"""Replay short IPE-C rescue rules on the existing exact endpoint pool."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from freeze import METHODS, matched, verify_allocated_labels


def replay(base):
    archive = base / "ipe_c_two_endpoint_completion_v1/RESULTS.json"
    rows = json.loads(archive.read_bytes())["rows"]
    verify_allocated_labels(archive.resolve(), rows)
    formal = base / "rpeval_formal_multi_coverage_v1"
    predictions = {r["uid"]: r for r in json.loads(
        (formal / "RPR_RANK_FUSION_AUDIT_300.json").read_bytes())["rows"]}
    full = {r["uid"]: r for r in json.loads((formal / "RESULT_ROWS.json").read_bytes())
            if r["method"] == "RPR_PAPER_FULL"}
    arms = defaultdict(lambda: defaultdict(Counter))
    common = 0
    for row in rows:
        uid, labels = row["uid"], row["labels"]
        if any(matched(row, m) is None for m in METHODS):
            continue
        common += 1
        record = predictions[uid]
        policies = record["policies"]
        ipe, mle, fused = (policies[key]["policy"] for key in ("IPE_ONLY", "MLE_ONLY", "PAPER_FUSION"))
        original = row["old_route"] == "REUSE_RP"
        if (len(ipe) != len(mle) or len(ipe) != len(fused) or len(ipe) != len(labels)
                or original != ("C" in ipe)
                or policies["PAPER_FUSION"]["actor_request_sha256"] != full[uid]["actor_request_sha256"]):
            raise ValueError("Stored policies or scored endpoint disagree with the original wire")
        if original:
            continue
        labels_slice = "contains_C" if "C" in labels else "only_B" if "B" in labels else "all_A"
        rule = {
            "either_estimator_C": "C" in mle,
            "same_source_ipe_B_mle_C": any(a == "B" and b == "C" for a, b in zip(ipe, mle)),
            "same_source_ipe_B_mle_fused_C": any(a == "B" and b == c == "C" for a, b, c in zip(ipe, mle, fused)),
        }
        first, rescue = (row["scores"][m]["grade"] for m in ("IPE_C", "RPR_PAPER_FULL"))
        for name, fires in rule.items():
            if not fires:
                continue
            delta = rescue["match"]["matched"] - first["match"]["matched"]
            for bucket in ("overall", labels_slice, row["scope"]):
                arm = arms[name][bucket]
                arm.update(tasks=1, positions=len(labels), match_delta=delta,
                           exact_delta=rescue["full_match"] - first["full_match"],
                           win=delta > 0, loss=delta < 0, tie=delta == 0)
                for metric in ("OPB", "UPB", "FM"):
                    if metric in first and metric in rescue:
                        arm.update({f"{metric}_delta": rescue[metric] - first[metric],
                                    f"{metric}_paired_tasks": 1})
    return {"common_tasks": common, "rules": arms}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("research_report_root", type=Path)
    print(json.dumps(replay(parser.parse_args().research_report_root), indent=2, sort_keys=True))
