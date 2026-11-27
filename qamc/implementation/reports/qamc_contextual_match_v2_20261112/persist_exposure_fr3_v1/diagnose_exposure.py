"""Read-only exposure and paired state diagnostics on settled repeat positions."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

RUNS = Path("runs/qamc_contextual_match_v2_20261112")
RUN = RUNS / "persist_exposure_fr3_v1"
SAFETY = RUNS / "persist_equal_cap_safety_v1"
REPEATED = RUNS / "persist_repeated_deployment_v1"
BU = "beneficial_memory_usage"
ARMS = ("SELECTED", "GROUP", "FULL", "EMPTY", "RUBRIC")
BATCHES = tuple(part + str(repeat) for part in ("Matched", "Remaining") for repeat in (1, 2, 3))


def read(path):
    return json.loads(path.read_text())


def rating(score):
    return score["rating"] if score is not None else None


def archived_risk():
    roster = read(SAFETY / "FROZEN.json")["tracks"]
    earlier = defaultdict(dict)
    for repeat in (1, 2):
        for row in read(SAFETY / f"WAVE{repeat}.json")["rows"]:
            earlier[row["uid"], repeat][row["arm"]] = row
    third = {r["uid"]: r for r in read(REPEATED / "DRAW3.json")["rows"]
             if r["method"] == "SELECTED_GEPA"}
    assert third.keys() == roster.keys()
    answer = {}
    losses = []
    for uid, track in sorted(roster.items()):
        selected, group, sources = [], [], []
        for repeat in (1, 2):
            pair = earlier[uid, repeat]
            arm = pair["ROUTED"]
            peer = pair["FULL" if arm["selected_count"] else "EMPTY"]
            selected.append(rating(arm["score"]))
            group.append(rating(peer["score"]))
            sources.append([arm["selected_count"], arm["selected_sha256"]])
            if selected[-1] >= 3 > group[-1]:
                losses.append((uid, repeat))
        later = third[uid]
        selected.append(rating(later["score"]))
        # The nonempty third-draw whole-history comparator requires an
        # independently registered compatible sample from the current run.
        group.append(selected[-1] if later["selected_count"] == 0 else None)
        sources.append([later["selected_count"], later["selected_sha256"]])
        answer[uid] = {"track": track, "selected": selected, "group": group, "sources": sources}
    return {"rows": answer, "single_draw_negative": losses}


def third_difference_bounds(rows):
    """Protect the coupled missing third draw where the wire is shared."""
    bounds = defaultdict(lambda: [0, 0])
    for row in rows.values():
        a, b = row["selected"], row["group"]
        first_a = int(any(v >= 3 for v in a[:2]))
        first_b = int(any(v >= 3 for v in b[:2]))
        third_a = (0, 1) if a[2] is None else (int(a[2] >= 3),)
        third_b = (0, 1) if b[2] is None else (int(b[2] >= 3),)
        pairs = ([(flag, flag) for flag in third_a] if row["sources"][2][0] == 0
                 else list(product(third_a, third_b)))
        differences = [max(first_a, x) - max(first_b, y) for x, y in pairs]
        tally = bounds[row["track"]]
        tally[0] += min(differences)
        tally[1] += max(differences)
    return dict(bounds)


def publishable_risk(old):
    rows = {}
    distinct = defaultdict(Counter)
    for uid, row in old["rows"].items():
        counts = [count for count, _ in row["sources"]]
        pools = [digest for _, digest in row["sources"]]
        if 0 in counts and any(counts):
            kind = "opened_and_closed"
        elif len(set(pools)) > 1:
            kind = "nonempty_sources_changed"
        else:
            kind = "same_source_list"
        if counts[2]:
            distinct[row["track"]][kind] += 1
        rows[sha256(uid.encode()).hexdigest()[:12]] = {
            "track": row["track"], "subsets": counts, "change": kind,
            "selected_ratings": row["selected"], "group_ratings": row["group"],
        }
    return {"archived_risk_rows": rows, "third_nonempty_by_track_and_change": distinct,
            "third_failure_difference_bounds_selected_minus_group": third_difference_bounds(old["rows"]),
            "archived_negative_positions": len(old["single_draw_negative"])}


def compare_methods(row, left, right):
    branch = row["exposure"]
    if not branch:
        return "exposure_unknown"
    if branch["selected_equals_group"]:
        return "shared_actor"
    a, b = (rating(row["methods"][name]["score"]) for name in (left, right))
    if a is None or b is None:
        return "score_unknown"
    if row["track"] == BU:
        x, y = a != 3, b != 3
    else:
        x, y = a >= 3, b >= 3
    return "loss" if x > y else "win" if x < y else "tie"


def settled_metrics():
    totals = Counter()
    observations = defaultdict(Counter)
    groups = defaultdict(set)
    ledger, identities = [], set()
    finished = []
    for label in BATCHES:
        p = RUN / (label + "_SETTLED.json")
        if not p.exists():
            continue
        data = read(p)
        identity = json.dumps(data["identity"], sort_keys=True)
        identities.add(identity)
        finished.append(label)
        ledger.extend(data["ledger"])
        for row in data["rows"]:
            track, uid = row["track"], row["uid"]
            totals[track] += 1
            observations[track][compare_methods(row, "SELECTED", "GROUP")] += 1
            if row["exposure"] and not row["exposure"]["selected_equals_group"]:
                groups[track].add(uid)
    if len(identities) > 1:
        raise ValueError("The settled batches do not share one experiment identity")
    return {
        "settled_batches": finished, "repetitions_by_track": totals,
        "selected_vs_group_by_position": observations,
        "distinct_roots_with_different_actual_exposure": {k: len(v) for k, v in groups.items()},
        "new_requests_with_settled_batches": len(ledger),
        "new_request_statuses": Counter(r["status"] for r in ledger),
        "new_reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in ledger),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-ids", action="store_true",
                        help="Use only in the private research checkout")
    args = parser.parse_args()
    archived = archived_risk()
    print(json.dumps({"archive": archived if args.private_ids else publishable_risk(archived),
                      "new": settled_metrics()}, ensure_ascii=False, sort_keys=True, indent=2))
