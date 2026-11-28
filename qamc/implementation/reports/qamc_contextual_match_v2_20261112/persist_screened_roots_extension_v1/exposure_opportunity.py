"""Count when partial history changes observed risk outcomes on the two exposed panels."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

import repeat as study
from repeat_readout import audit


def summarize_roots(roots):
    answer = Counter()
    for rows in roots.values():
        answer["root_count"] += 1
        distinct_wire = False
        ratings = defaultdict(list)
        for row in rows:
            distinct_wire |= row["distinct_wire"]
            states = {arm: study.risk_state([rating]) for arm, rating in row["ratings"].items()}
            if row["distinct_wire"]:
                key = "distinct_draw/" + "/".join(states[arm] for arm in ("SELECTED", "GROUP", "EMPTY"))
                answer[key] += 1
            for arm, rating in row["ratings"].items():
                ratings[arm].append(rating)
        states = {arm: study.risk_state(values) for arm, values in ratings.items()}
        if states["SELECTED"] == "pass" and states["GROUP"] == "fail":
            answer[f"selected_root_win_vs_group/empty_{states['EMPTY']}"] += 1
        answer["roots_with_any_distinct_wire"] += distinct_wire
    return dict(answer)


def previous_panel():
    artifact = study.RUN.with_name("persist_exposure_fr3_v1") / "RESULTS.json"
    old = study.read(artifact)["rows"]
    tracks = defaultdict(lambda: defaultdict(list))
    for row in old:
        if row["track"] not in ("sycophancy", "cross_domain"):
            continue
        ratings = {arm: (cell["score"] or {}).get("rating") for arm, cell in row["methods"].items()}
        tracks[row["track"]][row["uid"]].append({
            "draw": row["repeat"],
            "distinct_wire": not row["exposure"]["selected_equals_group"],
            "ratings": ratings,
        })
    if {track: len(roots) for track, roots in tracks.items()} != {"sycophancy": 12, "cross_domain": 19}:
        raise ValueError("Earlier risk roster mismatch")
    if any(sorted(row["draw"] for row in rows) != [1, 2, 3]
           for roots in tracks.values() for rows in roots.values()):
        raise ValueError("Earlier risk draw denominator mismatch")
    return tracks


def extension():
    checked = audit(list(study.WAVES))
    _, first, mapping, _, _ = study.prepare_repeat()
    roots = {}
    for uid, by_arm in checked["trajectories"].items():
        selected, group = (mapping[uid, arm] for arm in ("SELECTED", "GROUP"))
        if selected is None or group is None:
            raise ValueError("First-draw SELECTED versus GROUP comparison was not complete")
        distinct = selected != group
        roots[uid] = [{"distinct_wire": distinct,
                       "ratings": {arm: values[draw] for arm, values in by_arm.items()}}
                      for draw in range(len(study.WAVES) + 1)]
    if len(roots) != len(first):
        raise ValueError("Extension risk denominator mismatch")
    return roots


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--previous-only", action="store_true")
    args = parser.parse_args()
    panels = previous_panel()
    earlier = {track: summarize_roots(roots) for track, roots in panels.items()}
    result = {"previous_panel": earlier}
    if not args.previous_only:
        later = extension()
        if set(later) & {uid for roots in panels.values() for uid in roots}:
            raise ValueError("Panels overlap")
        result["fixed_exposure_extension"] = summarize_roots(later)
    print(json.dumps(result, sort_keys=True, indent=2))
