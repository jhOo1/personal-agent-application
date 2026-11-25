"""Bound archived Match gains from a repair limited to already usable B/C sources."""
from collections import Counter
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
MAIN = "SAME_DRAFT_MAIN_ONLY"
GATE, RP = "GEPA_SELECTED_BOUNDS", "RPR_PAPER_FULL"
USABLE_IN_MAIN = {"GUARD", "STYLE_OR_CONTENT", "OPTIONAL"}


def read(path, collection):
    rows = json.loads((BASE / path).read_text())[collection]
    indexed = {row["uid"]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError(f"Duplicate cases in {path}")
    return indexed


def headroom(scored, coverage, rubric, opponent, panel):
    total = Counter()
    groups, scope_groups = set(), set()
    for uid, row in scored.items():
        main = row["native"][MAIN]["fields"].get("match")
        other = row["native"][opponent]["fields"].get("match")
        if main is None or other is None:
            continue
        flagged = any(rubric[uid]["cells"][arm]["flags"] for arm in (MAIN, opponent))
        if panel == "without_detected_warnings" and flagged:
            continue
        if panel == "less_exposed" and not row["less_exposed"]:
            continue

        n, achieved = main["positions"], main["matched"]
        if n != len(row["labels"]) or n != other["positions"] or not (0 <= achieved <= n and 0 <= other["matched"] <= n):
            raise ValueError(f"Invalid common Match score for {uid}")
        groups.add(row["group"])
        delta = achieved - other["matched"]
        total.update(roots=1, positions=n, main=achieved, opponent=other["matched"])
        if uid not in coverage:
            total.update(all_a_roots=1, all_a_delta=delta)
            continue

        total.update(mixed_roots=1, mixed_delta=delta)
        trace = coverage[uid]
        allowed = [p["author_label"] for p in trace["positions"].values() if p["main_contract"] in USABLE_IN_MAIN]
        errors = n - achieved
        total["max_gain_usable_bc"] += min(errors, len(allowed))
        total["max_gain_usable_b_only"] += min(errors, allowed.count("B"))
        total["max_gain_usable_c_only"] += min(errors, allowed.count("C"))
        if trace["comparison"] == "WORSE" and len(allowed) == len(trace["positions"]):
            total.update(gate_upb_worse_all_usable_roots=1, max_gain_in_worse_group=min(errors, len(allowed)))
            scope_groups.add(row["group"])

    return dict(total, source_groups=len(groups), worse_scope_source_groups=len(scope_groups),
                main_minus_opponent=total["main"] - total["opponent"])


def audit():
    scored = read("decision_realization_append_ablation_v1/SETTLED.json", "rows")
    coverage = read("decision_optional_release_rpeval_v1/MAIN_COVERAGE_AUDIT.json", "cases")
    rubric = read("decision_main_recall_audit_v1/RUBRIC_AUDIT.json", "cases")
    if scored.keys() != rubric.keys() or coverage.keys() != {uid for uid, row in scored.items() if set(row["labels"]) != {"A"}}:
        raise ValueError("Archive rosters differ")
    for uid, row in scored.items():
        diagnosis = rubric[uid]
        if (row["group"], row["labels"]) != (diagnosis["group"], diagnosis["labels"]):
            raise ValueError(f"Rubric attached to different task: {uid}")
        if uid in coverage:
            trace = coverage[uid]
            expected = Counter(label for label in row["labels"] if label != "A")
            if trace["group"] != row["group"] or Counter(p["author_label"] for p in trace["positions"].values()) != expected:
                raise ValueError(f"Legal source coverage attached to different task: {uid}")
    panels = ("all", "without_detected_warnings", "less_exposed")
    return {opponent: {panel: headroom(scored, coverage, rubric, opponent, panel) for panel in panels}
            for opponent in (RP, GATE)}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
