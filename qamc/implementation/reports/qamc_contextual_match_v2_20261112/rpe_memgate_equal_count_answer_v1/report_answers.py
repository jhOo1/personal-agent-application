"""Compute exact paired score and selected-source diagnostics after settlement."""
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs" / HERE.parent.name / HERE.name
ARMS = ("ZH_GATE", "EN_GATE", "EN_COSINE")
METRICS = ("OPB", "UPB", "FM")
PAIRS = (("EN_GATE", "ZH_GATE"), ("EN_COSINE", "ZH_GATE"), ("EN_COSINE", "EN_GATE"),
         *((name, control) for name in ARMS for control in ("IPE_C", "DIRECT_ZH", "RPR_PAPER_FULL")))


def read(path):
    return json.loads(path.read_text())


def slice_name(labels):
    if set(labels) == {"A"}:
        return "ALL_A"
    return "CONTAINS_C" if "C" in labels else "ONLY_B"


def score_of(row, method):
    if method in ARMS:
        return row["arms"][method]["score"]
    return row["controls"][method]


def match(cell, n):
    if cell is None or not (m := cell["grade"].get("match")):
        return None
    if m["positions"] != n or not 0 <= m["matched"] <= n:
        raise ValueError("Outcome has a different original position count")
    return m["matched"]


def compare(rows, first, second):
    outcomes, clean, length = Counter(), Counter(), Counter()
    by_stratum = defaultdict(Counter)
    severity = defaultdict(Counter)
    lower = upper = 0
    for row in rows:
        labels = row["labels"]
        n = len(labels)
        a, b = score_of(row, first), score_of(row, second)
        x, y = match(a, n), match(b, n)
        lower += (x if x is not None else 0) - (y if y is not None else n)
        upper += (x if x is not None else n) - (y if y is not None else 0)
        if x is None or y is None:
            continue
        count = dict(tasks=1, positions=n, first=x, second=y,
                     wins=x > y, losses=x < y, ties=x == y)
        outcomes.update(count)
        by_stratum[slice_name(labels)].update(count)
        if a["flags"] == b["flags"] == []:
            clean.update(count)
        if first in ARMS and second in ARMS:
            ca, cb = (row["arms"][arm]["original_characters"] for arm in (first, second))
            if abs(ca - cb) * 10 <= max(ca, cb):
                length.update(count)
        for key in METRICS:
            if key in a["grade"] and key in b["grade"]:
                severity[key].update(tasks=1, first=a["grade"][key], second=b["grade"][key])
    return {"match": outcomes, "by_task_stratum": by_stratum, "severity": severity,
            "flag_excluded": clean, "character_balanced": length,
            "all_allocated_match_difference_bounds": [lower, upper],
            "allocation": {"tasks": len(rows), "positions": sum(len(r["labels"]) for r in rows)}}


def report(results):
    rows, ledger = results["rows"], results["ledger"]
    if len(rows) != 24 or len({r["uid"] for r in rows}) != 24 or len({r["group_id"] for r in rows}) != 24:
        raise ValueError("Expected all tasks with distinct frozen source groups")
    exposure, lengths, runtime, tokens = defaultdict(Counter), defaultdict(list), defaultdict(Counter), defaultdict(list)
    paired_controls = Counter()
    actual_usage = {r["request_sha256"]: r["usage"] for r in ledger
                    if r["unit"]["stage"] == "EqualCountActor" and r.get("usage")}
    for row in rows:
        labels = row["labels"]
        if not labels or set(labels) - {"A", "B", "C"}:
            raise ValueError("Invalid confirmed author labels")
        counts = {len(r["ids"]) for r in row["arms"].values()}
        if len(counts) != 1:
            raise ValueError("Different exposure counts on a matched comparison")
        for arm in ARMS:
            cell = row["arms"][arm]
            runtime[arm][cell["status"]] += 1
            lengths[arm].append(cell["original_characters"])
            usage = actual_usage.get(cell["request_sha256"], {})
            count = usage.get("prompt_tokens", usage.get("input_tokens"))
            if count is not None:
                tokens[arm].append(count)
            for i, label in enumerate(labels):
                exposure[arm][label + "_available"] += 1
                exposure[arm][label + "_visible"] += f"M{i}" in cell["ids"]
        for a, b in combinations(ARMS, 2):
            if row["arms"][a]["request_sha256"] == row["arms"][b]["request_sha256"]:
                if row["arms"][a]["score"] != row["arms"][b]["score"]:
                    raise ValueError("Identical requests have diverging grades")
                paired_controls[f"{a}/{b}"] += 1
    return {"comparisons": {f"{a}/{b}": compare(rows, a, b) for a, b in PAIRS},
            "exposure": exposure, "arm_status": runtime, "exact_shared": paired_controls,
            "original_selected_characters": {arm: {"median": median(v), "total": sum(v)} for arm, v in lengths.items()},
            "physical_actor_input_tokens_by_arm": {arm: {"reported_tasks": len(tokens[arm]), "total": sum(tokens[arm])}
                                                   for arm in ARMS},
            "new_physical_requests": Counter(r["unit"]["stage"] for r in ledger),
            "request_status": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger)}


if __name__ == "__main__":
    print(json.dumps(report(read(RUN / "RESULTS.json")), sort_keys=True, indent=2))
