"""Measure recorded tradeoffs within the exact previously tested fusion pool."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evo_qamc_fit_v1"))

from decision_quarantined_synthesis import ARMS, PRIVATE, metrics, prepare, read


def score_vector(domain, value):
    if domain == "RPEval":
        return (value["primary"], -value["OPB"], -value["UPB"], -value["FM"])
    if domain == "BenchPreS":
        return (value["primary"], -value["MR"], value["completeness"])
    return (value["primary"],)


def dominates(left, right):
    return all(a >= b for a, b in zip(left, right, strict=True)) and left != right


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--local-case-ids", action="store_true")
    args = parser.parse_args()
    pin, panel = prepare()
    if pin != read(PRIVATE / "FROZEN.json"):
        raise ValueError("Fusion roster or request inputs changed")
    result = read(PRIVATE / "RESULTS.json")
    grouped = defaultdict(dict)
    for row in result["rows"]:
        key = row["method"]
        arm = grouped[row["uid"]]
        if key in arm:
            raise ValueError("Duplicate settled arm")
        arm[key] = row
    if set(grouped) != set(panel):
        raise ValueError("Fusion settlement coverage does not match the roster")
    counts = defaultdict(Counter)
    for uid, entry in panel.items():
        card = entry["card"]
        domain = card["domain"]
        track = f"{domain}/{card['stratum']}" if domain == "PersistBench" else domain
        cell = counts[track]
        cell["assigned"] += 1
        cell["capacity_eligible"] += entry["capacity_eligible"]
        if set(grouped[uid]) != set(ARMS):
            raise ValueError("Expected three logical fusion arms")
        pool_rows = entry["originals"]
        pool_metrics = [metrics(card, row["score"]) for row in pool_rows]
        base = metrics(card, card["base_score"])
        if any(value is None for value in [base, *pool_metrics]):
            raise ValueError("Expected verified archived scores for every assigned root")
        old = score_vector(domain, base)
        pool = {score_vector(domain, value) for value in pool_metrics}
        best = max(vector[0] for vector in pool)
        front = {v for v in pool if not any(dominates(w, v) for w in pool)}
        cell["multiple_candidate_texts"] += len(entry["candidates"]) > 1
        cell["multiple_nondominated_score_vectors"] += len(front) > 1
        cell["candidate_primary_above_specialist"] += best > old[0]
        cell["candidate_protected_primary_above_specialist"] += any(
            v[0] > old[0] and dominates(v, old) for v in pool
        )
        cell["specialist_strictly_dominates_all_candidates"] += all(
            dominates(old, v) for v in pool
        )
        component_maxima = tuple(max(column) for column in zip(*pool, strict=True))
        cell["candidate_metricwise_gap"] += component_maxima not in pool
        if args.local_case_ids and (component_maxima not in pool or best > old[0]):
            print(uid, "specialist:", old, "candidates:", sorted(pool), file=sys.stderr)
        for arm, row in grouped[uid].items():
            new = metrics(card, row["score"])
            cell[f"{arm}/graded"] += new is not None
            if new is None:
                continue
            vector = score_vector(domain, new)
            cell[f"{arm}/above_all_primary"] += vector[0] > max(best, old[0])
            cell[f"{arm}/protected_primary_gain"] += vector[0] > old[0] and dominates(vector, old)
            cell[f"{arm}/dominated_by_specialist"] += dominates(old, vector)
            cell[f"{arm}/dominated_by_candidate"] += any(dominates(v, vector) for v in pool)
        cell["mask_changed_wire"] += grouped[uid]["QUARANTINED_FUSION"]["mask_changed_wire"]
    print(json.dumps({"new_requests": 0, "tracks": counts}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
