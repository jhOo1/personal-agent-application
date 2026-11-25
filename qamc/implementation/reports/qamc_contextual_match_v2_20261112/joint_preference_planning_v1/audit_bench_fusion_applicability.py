"""Compare policy admission with BenchPreS rubric applicability by exact source text."""
from collections import Counter, defaultdict
import json
import re

from qamc.pa.core import digest

from audit_asymmetric_fusion_transfer import audit as fusion_transfer
from settle_realization_transfer import paired_summary
from transfer_edit import bench, context, development_roots, read


def normalize(text):
    return " ".join(text.casefold().split()).rstrip(".")


def audit():
    cases, _, _ = context("BenchPreS")
    roots = {r["uid"]: r for r in development_roots("BenchPreS")}
    policy = {r["uid"]: r for r in fusion_transfer("BenchPreS")["rows"]}
    if cases.keys() != roots.keys() or policy.keys() != roots.keys():
        raise ValueError("Unexpected exposed policy or evaluation roster")
    counts, nonbold, grouped, traces = defaultdict(Counter), defaultdict(Counter), defaultdict(list), []
    for uid, case in cases.items():
        evaluation = read(bench.ROOT / case["evaluation_path"])
        if digest(evaluation) != case["evaluation_hash"]:
            raise ValueError("BenchPreS rubric no longer matches the archived hash")
        root = roots[uid]
        evidence = [normalize(entry["text"]) for entry in root["original_sources"]]
        assigned = policy[uid]
        for attr, applicable in zip(evaluation["preference_attribute"], evaluation["preference_label"], strict=True):
            if type(applicable) is not bool:
                raise ValueError("Expected the public benchmark's applicability annotations")
            hits = [index for index, source in enumerate(evidence) if normalize(attr) == source]
            if len(hits) != 1:
                raise ValueError(f"Preference source match is not unique for {uid}")
            pos, = hits
            original, new = assigned["before"][pos], assigned["after"][pos]
            controls = {"rp": original,
                        "predicted_hard_router": original if "C" in assigned["before"] else "A",
                        "task_first": new}
            for arm, label in controls.items():
                denominator, numerator = ("applicable", "true_retained") if applicable else (
                    "inapplicable", "false_retained")
                counts[arm][denominator] += 1
                counts[arm][numerator] += label != "A"
                if not re.search(r"\bbold\s+text\b", attr, re.I):
                    nonbold[arm][denominator] += 1
                    nonbold[arm][numerator] += label != "A"
            group = case["analysis_group_id"]
            partition = "applicable_recall" if applicable else "inapplicable_release"
            grouped[partition].append((group, original != "A", new != "A", 1))
            if original != new:
                traces.append({"uid": uid, "source_id": root["original_sources"][pos]["memory_id"],
                               "attribute": attr, "applicable": applicable, "rp": original, "task_first": new})
    if sum(len(rows) for rows in grouped.values()) != 240:
        raise ValueError("Expected 240 evaluated attributes")
    intervals = {}
    for metric, rows in grouped.items():
        interval = paired_summary(rows)
        interval["attributes"] = interval.pop("roots")
        intervals[metric] = interval
    return {"cases": len(cases), "physical_requests": 0, "method_counts": counts,
            "nonbold_method_counts": nonbold, "pairwise": intervals,
            "changed_source_grades": traces}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
