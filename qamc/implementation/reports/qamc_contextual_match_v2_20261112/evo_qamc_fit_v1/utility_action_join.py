"""Join blind behavior decisions to frozen source exposure and old grades, locally only."""
from collections import Counter
import json

from qamc.common import sha
from utility_action_review import AXES, FILES, ROOT, RUN, SOURCE, probe, require

ARMS = ("SELECTED", "FULL")


def reading(states, supported):
    a, b = states
    if a == b == "MET":
        return "both_met"
    if "UNKNOWN" in states:
        return "unresolved"
    if a == "MET":
        return "selected_only_met"
    if b == "MET":
        return "full_only_source_in_both" if supported else "full_only_source_missing_selected"
    return "neither_met"


def main():
    cards, answers, key = (probe.read(SOURCE / name) for name in FILES)
    exposures = probe.read(SOURCE / "UNBLIND_SOURCES.json")
    native = probe.read(ROOT / "persist_utility_fresh_deployment_v1/private/SETTLED.json")
    scores = {(row["uid"], row["arm"]): row for row in native["rows"]}
    criteria = probe.read(RUN / "FINAL_CRITERIA.json")
    require(set(cards) == set(answers) == set(key) == set(exposures), "unaligned packets")
    require(len({row["group"] for row in key.values()}) == len(key), "source group repeated")
    summaries = {axis: Counter() for axis in AXES}
    by_native = {axis: Counter() for axis in AXES}
    private_rows = {}
    for packet, identity in key.items():
        aid = {p["arm"]: p["answer_id"] for p in identity["positions"]}
        for position in identity["positions"]:
            require(sha(answers[packet][position["answer_id"]]) == position["answer_sha256"], "answer drift")
        grade = {judge: [scores[identity["uid"], arm][judge] for arm in ARMS] for judge in ("GPT", "Qwen")}
        visible = exposures[packet]
        original_ids = {source["id"] for source in cards[packet]["history"]}
        require(set(visible["FULL"]) == original_ids, "full source set changed")
        require(set(visible["SELECTED"]) <= original_ids, "unknown selected source")
        require(len(visible["SELECTED"]) == scores[identity["uid"], "SELECTED"]["selection_count"], "selection count changed")
        vote_path = RUN / "review" / "Blind" / sha(packet) / "vote.json"
        vote = probe.read(vote_path) if vote_path.exists() else None
        private_rows[packet] = {"grades": grade, "axes": {}}
        for axis in AXES:
            status = "no_review"
            if vote is not None:
                criterion = criteria[packet][axis]
                if criterion is None:
                    status = "not_applicable"
                else:
                    states = [vote[aid[arm]][axis]["state"] for arm in ARMS]
                    exposed = criterion["source"] in set(visible["SELECTED"]) | {"QUERY"}
                    status = reading(states, exposed)
                    private_rows[packet]["axes"][axis] = {"states": states, "selected_saw_anchor": exposed}
            summaries[axis][status] += 1
            if grade["Qwen"][0] in (1, 2) and grade["Qwen"][1] == 3:
                by_native[axis][status] += 1
    probe.freeze(RUN / "JOIN_PRIVATE.json", private_rows)
    total = {"exposure_diagnostic": summaries, "qwen_full_only_strict_pass": by_native}
    probe.freeze(RUN / "JOIN_AGGREGATE.json", total)
    print(json.dumps(total, sort_keys=True))


if __name__ == "__main__":
    import os
    os.umask(0o077)
    # Require a settled run so an in-progress snapshot cannot freeze an incomplete diagnosis.
    require((RUN / "AGGREGATE.json").exists(), "review not settled")
    main()
