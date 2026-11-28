"""Audit score headroom of actual distinct historical revisions against exact incumbents."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path
from runpy import run_path
import sys

BASE = Path(__file__).resolve().parent.parent
STUDIES = (
    "protected_clause_exposure_v1", "task_condition_branches_v1",
    "foil_anchored_decision_repair_v1", "participant_execution_preflight_v1",
)
old = run_path(str(BASE / STUDIES[0] / "trial.py"))
numeric = run_path(str(BASE / "foil_anchored_decision_repair_v1/public_summary.py"))["numeric_score"]
sha, read = old["sha"], old["read"]


def restore():
    archive = read(BASE / "transactional_reassembly_v1/FROZEN.json")
    if archive["exposed_development_only"] is not True:
        raise ValueError("Expected exposed development archive")
    cards = {row["uid"]: row for row in archive["rows"]}
    pin, selected, _ = old["build"]()
    if pin != read(old["PRIVATE"] / "FREEZE.json"):
        raise ValueError("Protected clause source manifest changed")
    protected = {uid: item["card"] for uid, item in selected.items()}
    for uid, card in protected.items():
        if uid not in cards:
            continue
        other = cards[uid]
        if card["baseline_answer_sha256"] != other["baseline_answer_sha256"]:
            raise ValueError("Incumbent hash differs across archives")
        if (vector(card, card["base_score"]) != vector(other, other["base_score"])
                or bool(card["base_flags"]) != bool(other["base_flags"])):
            raise ValueError("Incumbent grade or flag differs across archives")
    return cards | protected


def vector(row, score):
    if not score:
        return None
    domain = row["benchmark"]
    simple = {"benchmark": domain, "stratum": row["stratum"], "score": score}
    if domain == "RPEval":
        simple["score"] = score.get("match")
        simple["bias"] = {key: score.get(key) for key in ("OPB", "UPB", "FM")}
    fields = numeric(simple)
    if fields is None:
        return None
    if domain == "RPEval":
        if not all(isinstance(fields.get(key), int) for key in ("OPB", "UPB", "FM")):
            return None
        return (fields["matched"], -fields["OPB"], -fields["UPB"], -fields["FM"]), (fields["positions"],)
    if domain == "BenchPreS":
        return (fields["aar_numerator"], -fields["mr_numerator"], fields["task_completeness"],
                fields["nonbold_numerator"]), (fields["aar_denominator"], fields["mr_denominator"],
                                                fields["nonbold_denominator"])
    rating = fields["rating"]
    return (fields["pass"], rating if row["stratum"] == "beneficial_memory_usage" else -rating), (1,)


def main():
    args = ArgumentParser(description=__doc__)
    args.add_argument("--local-case-ids", action="store_true")
    choices = args.parse_args()
    cards = restore()
    run_root = old["RUN"].parent
    tracking = defaultdict(Counter)
    candidates = defaultdict(lambda: defaultdict(list))
    cases = set()
    groups = defaultdict(set)
    for study in STUDIES:
        result = read(run_root / study / "private" / "SETTLED.json")
        for row in result["rows"]:
            uid = row["uid"]
            base = cards[uid]
            if any(row[key] != base[key] for key in ("benchmark", "group", "stratum")):
                raise ValueError("Source identity mismatch")
            if sha(base["base_answer"]) != base["baseline_answer_sha256"]:
                raise ValueError("Baseline answer digest drift")
            track = f"{row['benchmark']}/{row['stratum']}" if row["benchmark"] == "PersistBench" else row["benchmark"]
            cases.add((track, uid))
            groups[track].add(row["group"])
            stats = tracking[track]
            stats["logical_cells"] += 1
            if not row.get("answer"):
                stats["missing_answers"] += 1
                continue
            digest = sha(row["answer"])
            if digest != row["answer_sha256"]:
                raise ValueError("Revised answer digest drift")
            if digest == base["baseline_answer_sha256"]:
                stats["exact_incumbent_cells"] += 1
                continue
            stats["changed_answer_cells"] += 1
            measured, incumbent = vector(row, row.get("score")), vector(row, base["base_score"])
            if measured is None or incumbent is None:
                stats["incomparable_changed_cells"] += 1
                continue
            if measured[1] != incumbent[1]:
                raise ValueError("Metric denominators do not align")
            candidates[track, uid][digest].append((measured[0], bool(row.get("score_flags"))))
    for track, uid in sorted(cases):
        base = cards[uid]
        stats = tracking[track]
        stats["distinct_tasks"] += 1
        old_vector, denominators = vector(base, base["base_score"])
        pool = candidates[track, uid]
        stats["distinct_scored_changed_answers"] += len(pool)
        stats["tasks_with_scored_changed_answer"] += bool(pool)
        consistent = []
        for observations in pool.values():
            values = {v for v, _ in observations}
            if len(values) > 1:
                stats["same_answer_score_conflicts"] += 1
                continue
            v = values.pop()
            unflagged = not any(flag for _, flag in observations) and not base["base_flags"]
            consistent.append((v, unflagged))
        win = [v for v, _ in consistent if v[0] > old_vector[0]]
        protected = [v for v, _ in consistent if v[0] > old_vector[0]
                     and all(a >= b for a, b in zip(v, old_vector, strict=True))]
        clean = [v for v, unflagged in consistent if unflagged and v in protected]
        secondary = [v for v, unflagged in consistent if unflagged and v[0] == old_vector[0]
                     and v != old_vector and all(a >= b for a, b in zip(v, old_vector, strict=True))]
        stats["tasks_with_unflagged_secondary_only_win"] += bool(secondary)
        stats["tasks_with_primary_win_in_pool"] += bool(win)
        stats["tasks_with_protected_primary_win_in_pool"] += bool(protected)
        stats["tasks_with_unflagged_protected_primary_win"] += bool(clean)
        stats["incumbent_primary"] += old_vector[0]
        stats["primary_denominator"] += denominators[0]
        stats["protected_oracle_primary"] += max([old_vector[0], *(v[0] for v in protected)])
        if choices.local_case_ids and (win or secondary):
            print(uid, "incumbent", old_vector, "wins", win, "protected", protected, "unflagged", clean, "secondary", secondary,
                  file=sys.stderr)
    for track, group_set in groups.items():
        tracking[track]["source_groups"] = len(group_set)
    print(json.dumps({"inputs": STUDIES, "new_requests": 0, "tracks": tracking}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
