"""Join saved PersistBench endpoints without issuing or changing grades."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def audit():
    panel = read(HERE / "SELECTED_GEPA_EXPANSION_PANEL.json")["cases"]
    uids = {row["uid"] for row in panel}
    waves = HERE.parent / "persist_author_controls_v2" / "waves"
    archived = {}
    for path in sorted(waves.glob("*.json")):
        for row in read(path)["rows"]:
            key = row["uid"], row["method"]
            if key[0] in uids and key[1] in {"PB_NO_MEMORY", "PB_RUBRIC"}:
                if key in archived:
                    raise ValueError(f"Duplicate archive row: {key}")
                archived[key] = row
    switch = {row["uid"]: row for row in read(
        HERE / "persist_switch_execution_v1" / "RESULTS.json")["rows"]
        if row["method"] == "ENFORCED_SWITCH"}
    if set(switch) != uids:
        raise ValueError("Switch and expansion rosters differ")
    by_category = {}
    for row in panel:
        uid, category = row["uid"], row["category"]
        baseline = archived[uid, "PB_RUBRIC"]
        if baseline["actor_request_sha256"] != row["actor_request_sha256"]:
            raise ValueError(f"Baseline request drift: {uid}")
        flag = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
        old, empty, current = baseline["score"], archived[uid, "PB_NO_MEMORY"]["score"], switch[uid]["score"]
        if switch[uid]["category"] != category or any(score is not None and score["category"] != category for score in (old, empty)):
            raise ValueError(f"Category mismatch: {uid}")
        if old[flag] != row["score"][flag]:
            raise ValueError(f"Baseline outcome drift: {uid}")
        counts = by_category.setdefault(category, Counter())
        counts["planned"] += 1
        counts["switch_on"] += switch[uid]["mode"] == "ON"
        if empty is None or current is None:
            counts["missing"] += 1
            continue
        counts.update({"common": 1, "rubric_pass": not old[flag], "empty_pass": not empty[flag],
                       "switch_pass": not current[flag]})
        counts["rubric_fail_repaired_by_both"] += old[flag] and not empty[flag] and not current[flag]
        counts["empty_fail_restored_by_switch"] += empty[flag] and not current[flag]
    return by_category


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
