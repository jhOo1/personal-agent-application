"""Aggregate the frozen same-Actor comparison without dispatch or raw-text export."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from random import Random

from qamc.pa.core import digest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FORMAL = HERE.parent / "rpeval_formal_multi_coverage_v1"
RUN = ROOT / "runs" / HERE.parent.name / HERE.name
ARM = "MEMGATE_RP_ACTOR"
CONTROLS = ("IPE_C", "TASK_ONLY", "RPR_PAPER_FULL")
METRICS = ("OPB", "UPB", "FM")


def read(path):
    return json.loads(path.read_text())


def author_labels():
    manifest = read(FORMAL / "MANIFEST_300.json")
    labels = {}
    for case in manifest:
        if case["independent_confirmation"]:
            raise ValueError("Unexpected confirmation task")
        ref = read(ROOT / case["evaluation_path"])
        value = ref["intent_type"]
        if digest(ref) != case["evaluation_hash"] or not value or set(value) - {"A", "B", "C"}:
            raise ValueError("Frozen evaluation reference changed")
        labels[case["uid"]] = value
    return labels


def stratum(labels):
    if set(labels) == {"A"}:
        return "ALL_A"
    return "CONTAINS_C" if "C" in labels else "ONLY_B"


def exposure(plan, author):
    by_stratum, by_label = defaultdict(Counter), defaultdict(Counter)
    for uid, available in author.items():
        bucket = by_stratum[stratum(available)]
        bucket["allocated_tasks"] += 1
        bucket["allocated_positions"] += len(available)
        if uid not in plan["selection"]:
            bucket["missing_contract"] += 1
            continue
        meta = plan["selection"][uid]
        if len(available) != meta["available"]:
            raise ValueError("Actual and annotated source shape differ")
        visible = set(meta["kept"])
        if visible - {f"M{i}" for i in range(len(available))}:
            raise ValueError("Unexpected original source ID")
        bucket[meta["shape"]] += 1
        for i, label in enumerate(available):
            by_label[label].update(verified=1, visible=f"M{i}" in visible)
    return {"by_stratum": by_stratum, "by_author_position": by_label}


def measure(cell, size):
    match = (cell or {}).get("grade", {}).get("match")
    if not match:
        return None
    matched = match["matched"]
    if match["positions"] != size or not 0 <= matched <= size:
        raise ValueError("Unexpected final Match denominator")
    return matched


def bootstrap(groups):
    values = list(groups.values())
    if len(values) < 2:
        return None
    rng = Random(20261126)
    draws = []
    for _ in range(5000):
        sampled = rng.choices(values, k=len(values))
        draws.append(round(100 * sum(s[0] for s in sampled) / sum(s[1] for s in sampled), 4))
    draws.sort()
    return [draws[124], draws[4874]]


def compare(rows, author, control, subset):
    pairs, metrics, groups, availability = Counter(), defaultdict(Counter), defaultdict(lambda: [0, 0]), Counter()
    clean = Counter()
    lower = upper = 0
    for row in rows:
        labels = author[row["uid"]]
        if subset != "ALL" and subset != stratum(labels):
            continue
        n = len(labels)
        if row["labels"] and list(row["labels"]) != list(labels):
            raise ValueError("Old and evaluated stratum differ")
        a, b = (row["scores"][key] for key in (ARM, control))
        x, y = measure(a, n), measure(b, n)
        availability.update(tasks=1, positions=n, both_missing=x is None and y is None,
                            memgate_missing=x is None, control_missing=y is None)
        lower += (x if x is not None else 0) - (y if y is not None else n)
        upper += (x if x is not None else n) - (y if y is not None else 0)
        if x is None or y is None:
            continue
        counts = dict(tasks=1, positions=n, memgate=x, control=y, wins=x > y, losses=x < y, ties=x == y)
        pairs.update(counts)
        group = groups[row["source_group"]]
        group[0] += x - y
        group[1] += n
        if a["flags"] == b["flags"] == []:
            clean.update(counts)
        for key in METRICS:
            if key in a["grade"] and key in b["grade"]:
                metrics[key].update(pairs=1, memgate=a["grade"][key], control=b["grade"][key])
    return {"allocation": availability, "match": pairs, "severity": metrics, "flag_excluded": clean,
            "groups": len(groups), "cluster_sensitivity_pp": bootstrap(groups),
            "all_planned_match_delta_bounds": [lower, upper]}


def report(selection_only):
    frozen = read(RUN / "PREFLIGHT_PRIVATE.json")
    labels = author_labels()
    out = {"exposure": exposure(frozen, labels)}
    if selection_only:
        return out
    completed = read(RUN / "RESULTS.json")
    rows = completed["rows"]
    if len(rows) != 300 or {r["uid"] for r in rows} != labels.keys():
        raise ValueError("Result omitted frozen tasks")
    out["comparisons"] = {
        control: {stratum: compare(rows, labels, control, stratum)
                  for stratum in ("ALL", "ALL_A", "ONLY_B", "CONTAINS_C")}
        for control in CONTROLS
    }
    out["execution"] = completed["summary"]
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-only", action="store_true")
    print(json.dumps(report(parser.parse_args().selection_only), indent=2, sort_keys=True))
