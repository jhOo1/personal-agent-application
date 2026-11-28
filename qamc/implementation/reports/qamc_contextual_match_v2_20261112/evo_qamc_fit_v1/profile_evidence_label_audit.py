"""Attribute source-presence changes from archived RPEval labels, offline only."""
from collections import Counter
import json
from pathlib import Path

from profile_evidence_audit import inspect_stage, user_data
from profile_evidence_restoration import CROSS, DIRECT, OUT, parse_profile, read

LABELS = Path(__file__).parents[1] / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json"


def audit():
    refs = {r["uid"]: r["sources"] for r in read(CROSS / "RESULTS.json")["rows"] if r["method"] == DIRECT}
    frozen_labels = {r["uid"]: r["labels"] for r in read(LABELS)["rows"]}
    manifests, receipts = inspect_stage(OUT, "RefinedProfile")
    totals, availability, task_types = Counter(), Counter(), {}
    for (uid, arm), wire in manifests.items():
        if not uid.startswith("rpeval/"):
            continue
        status, body = receipts.get((uid, arm), ("UNISSUED", None))
        availability[status] += 1
        if status != "OK":
            continue
        original = {item["memory_id"]: (item["text"], label) for item, label in
                    zip(refs[uid], frozen_labels[uid], strict=True)}
        history = user_data(wire)["source_evidence"]
        selected = {item["memory_id"] for item in history}
        if len(selected) != len(history) or any(
                original[item["memory_id"]][0] != item["text"] for item in history):
            raise ValueError("Refiner input is inconsistent with the original source and label ordering")
        try:
            points = parse_profile(body, history)
        except (KeyError, TypeError, ValueError):
            availability["INVALID_PROFILE_CONTRACT"] += 1
            continue
        observed = {p["source_id"] for p in points}
        if not observed <= selected:
            raise ValueError("Unexpected source backfill")
        labels = set(frozen_labels[uid])
        task_type = "all_A" if labels == {"A"} else "contains_C" if "C" in labels else "B_only"
        counts = task_types.setdefault(task_type, Counter())
        for collector in (counts, totals):
            collector["tasks"] += 1
            for name, subset in (("original_sources", original.keys()), ("selected_sources", selected),
                                 ("quoted_sources", observed)):
                for source in subset:
                    collector[name + "_" + original[source][1]] += 1
            collector["sources_with_multiple_points"] += len(points) - len(observed)
    return {"availability": availability, "totals": totals, "by_task_stratum": task_types}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
