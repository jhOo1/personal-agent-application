"""A single threshold fixed before aggregate extraction; all original missing outcomes persist."""
import json
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
archive = here.parents[2] / "runs" / here.parent.name / "persist_exposure_fr3_v1" / "RESULTS.json"
groups = defaultdict(lambda: defaultdict(dict))
summary = defaultdict(Counter)

def outcome(ratings, utility):
    if utility:
        assert len(ratings) == 1
        rating = ratings[0]
        return "unknown" if rating is None else "pass" if rating == 3 else "fail"
    if any(r is not None and r >= 3 for r in ratings):
        return "fail"
    return "unknown" if None in ratings else "pass"

def paired(before, after):
    if "unknown" in (before, after):
        return "unknown"
    return "tie" if before == after else "win" if after == "pass" else "loss"

for row in json.loads(archive.read_text())["rows"]:
    track, uid = row["track"], row["uid"]
    exposure = row["exposure"]
    trigger = exposure is not None and exposure["count"] == 1
    selected = row["methods"]["SELECTED"]
    candidate = row["methods"]["EMPTY"] if trigger else selected
    ratings = [cell["score"]["rating"] if cell["score"] else None for cell in (selected, candidate)]
    if exposure is None:
        assert ratings == [None, None]
    assert row["repeat"] not in groups[track][uid]
    groups[track][uid][row["repeat"]] = (trigger, ratings)
    if trigger:
        summary[track]["trigger_draws"] += 1
        comparison = paired(*(outcome([r], track == "beneficial_memory_usage") for r in ratings))
        summary[track]["draw_" + comparison] += 1

for track, roots in groups.items():
    utility = track == "beneficial_memory_usage"
    for uid, draws in roots.items():
        assert set(draws) == ({1} if utility else {1, 2, 3})
        affected = any(trigger for trigger, _ in draws.values())
        before, after = (outcome([v[1][i] for v in draws.values()], utility) for i in range(2))
        stats = summary[track]
        stats["roots"] += 1
        stats["trigger_roots"] += int(affected)
        stats["selected_" + before] += 1
        stats["candidate_" + after] += 1
        if affected:
            stats["affected_root_" + paired(before, after)] += 1
assert sum(len(v) for v in groups.values()) == 49
fresh_path = archive.parents[1] / "persist_utility_fresh_deployment_v1/private/SETTLED.json"
fresh = [r for r in json.loads(fresh_path.read_text())["rows"] if r["arm"] == "SELECTED"]
assert len({r["uid"] for r in fresh}) == len(fresh) == 18
summary["fresh_utility_trigger_coverage"] = dict(Counter(str(r["selection_count"]) for r in fresh))
print(json.dumps(summary, indent=2, sort_keys=True))
