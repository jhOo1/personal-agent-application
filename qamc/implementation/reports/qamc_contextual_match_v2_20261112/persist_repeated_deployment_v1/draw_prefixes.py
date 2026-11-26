"""Compare failure trajectories across settled PersistBench deployment waves."""
import argparse
from collections import Counter
import json
from pathlib import Path

from paired_bounds import compare

RUN = Path("runs/qamc_contextual_match_v2_20261112") / Path(__file__).parent.name
ACTIVE = "SELECTED_GEPA"
CONTROL = ("PB_RUBRIC", "PB_GEPA")
METHODS = (ACTIVE, *CONTROL)
BU = "beneficial_memory_usage"
TRACKS = ("cross_domain", "sycophancy", BU)


def failure(row):
    score = row["score"]
    if score is None:
        return None
    return score["failure_strict_utility" if row["category"] == BU else "failure_release"]


def outcome(sequence):
    if True in sequence:
        return "FAIL"
    return "UNKNOWN" if None in sequence else "PASS"


def build(cases, rows, waves):
    grid = {}
    for row in rows:
        uid, method, draw = row["uid"], row["method"], row["draw"]
        key = uid, method, draw
        if key in grid or row["category"] != cases.get(uid) or method not in METHODS:
            raise ValueError(f"Unexpected row {key}")
        grid[key] = failure(row)
    expected = {(uid, method, n) for uid, track in cases.items() for method in METHODS
                for n in range(1, (1 if track == BU else waves) + 1)}
    if grid.keys() != expected:
        raise ValueError("Settled checkpoints differ from the frozen allocation")

    output = {}
    for track in TRACKS:
        draws = 1 if track == BU else waves
        ids = [u for u, t in cases.items() if t == track]
        seq = {(u, m): [grid[u, m, k] for k in range(1, draws + 1)]
               for u in ids for m in METHODS}
        full = {m: {u for u in ids if None not in seq[u, m]} for m in METHODS}
        prefixes = {}
        for k in range(1, draws + 1):
            status = {key: outcome(vals[:k]) for key, vals in seq.items()}
            transitions = {}
            for m in METHODS:
                values = [seq[u, m] for u in ids]
                at_risk = [v for v in values if v[:k-1] == [False] * (k-1)]
                transitions[m] = {
                    "prefix_outcomes": Counter(status[u, m] for u in ids),
                    "prior_complete_passes": len(at_risk),
                    "new_known_failures_after_passes": sum(v[k-1] is True for v in at_risk),
                    "new_missing_after_passes": sum(v[k-1] is None for v in at_risk),
                }
            pairs = {}
            for m in CONTROL:
                matrix = Counter(f"{status[u, ACTIVE]}/{status[u, m]}" for u in ids)
                fixed = full[ACTIVE] & full[m]
                pairs[m] = {
                    "known_vs_missing": compare(matrix),
                    "fixed_complete_pair_tasks": len(fixed),
                    "fixed_complete_pair_candidate_failures": sum(status[u, ACTIVE] == "FAIL" for u in fixed),
                    "fixed_complete_pair_reference_failures": sum(status[u, m] == "FAIL" for u in fixed),
                }
            prefixes[str(k)] = {"per_method": transitions, "pairs": pairs}
        output[track] = prefixes
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("waves", type=int, choices=(1, 2, 3))
    args = parser.parse_args()
    plan = json.loads((RUN / "FROZEN.json").read_text())
    checkpoints = [json.loads((RUN / f"DRAW{n}.json").read_text()) for n in range(1, args.waves + 1)]
    execution = json.loads((RUN / "EXECUTION.json").read_text())
    if any(cp["identity"] != execution for cp in checkpoints):
        raise ValueError("Checkpoint identity changed between waves")
    rows = [row for cp in checkpoints for row in cp["rows"]]
    print(json.dumps(build(plan["cases"], rows, args.waves), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
