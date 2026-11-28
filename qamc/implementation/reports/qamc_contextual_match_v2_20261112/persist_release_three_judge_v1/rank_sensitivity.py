"""Compare paired external-system rankings on the same complete sources."""
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path
import sys

from summarize import JUDGES, decision


def compare(rows):
    tracks = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in rows:
        tracks[row["category"]][row["root"]][row["model"]].append(row)
    result = {}
    for category, roots in sorted(tracks.items()):
        models = sorted(next(iter(roots.values())))
        counts = {judge: dict.fromkeys(models, 0) for judge in JUDGES}
        eligible = 0
        utility = category == "beneficial_memory_usage"
        for per_model in roots.values():
            assert sorted(per_model) == models
            scores = {
                (model, judge): decision([row[judge] for row in draws], utility)
                for model, draws in per_model.items() for judge in JUDGES
            }
            if None in scores.values():
                continue
            eligible += 1
            for (model, judge), passed in scores.items():
                counts[judge][model] += passed
        comparisons = {}
        for judge in JUDGES[1:]:
            reverse, create_tie, break_tie = [], [], []
            for left, right in combinations(models, 2):
                released = counts["released"][left] - counts["released"][right]
                proxy = counts[judge][left] - counts[judge][right]
                if released * proxy < 0:
                    reverse.append([left, right])
                elif released and not proxy:
                    create_tie.append([left, right])
                elif proxy and not released:
                    break_tie.append([left, right])
            comparisons[judge] = {
                "strict_reversals": reverse,
                "released_strict_to_tie": create_tie,
                "released_tie_to_strict": break_tie,
            }
        result[category] = {
            "complete_sources_all_models": eligible,
            "allocated_sources": len(roots),
            "passes": counts,
            "rank_changes": comparisons,
        }
    return result


if __name__ == "__main__":
    saved = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(compare(saved["rows"]), indent=2))
