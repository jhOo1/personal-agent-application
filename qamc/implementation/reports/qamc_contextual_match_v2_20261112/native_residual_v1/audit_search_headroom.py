"""Count opportunities for feedback-driven native Actor optimization."""
from collections import Counter, defaultdict
import json

from build_jobs import archive_inputs, prepare
from summarize_reassembly import measure


def audit(wires, cards, allowed=None):
    counts, groups = defaultdict(Counter), defaultdict(set)
    for key, card in cards.items():
        if key not in wires or (allowed is not None and key not in allowed):
            continue
        benchmark = key[0]
        score = measure(benchmark, card["stratum"], card["base_score"])
        if score is None:
            counts[benchmark]["missing"] += 1
            continue
        counts[benchmark]["valid"] += 1
        gap = score["positions"] - score["primary"]
        counts[benchmark]["headroom"] += gap
        counts[benchmark]["with_gap" if gap else "at_ceiling"] += 1
        if gap:
            groups[benchmark].add(card["group"])
    return {benchmark: {**values, "groups_with_gap": len(groups[benchmark])}
            for benchmark, values in sorted(counts.items())}


if __name__ == "__main__":
    wires, cards = archive_inputs()
    eligible, search = prepare(("Measure search headroom.",), "search")
    print(json.dumps({"archived": audit(wires, cards),
                      "search_history_enabled": audit(wires, search, eligible)}, indent=2))
