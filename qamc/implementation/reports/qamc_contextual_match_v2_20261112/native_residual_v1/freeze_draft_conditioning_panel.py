"""Select source-distinct, previously exposed PersistBench endpoint contrasts."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTROLS = HERE.parent / "persist_author_controls_v2"
METHODS = ("PB_RUBRIC", "PB_NO_MEMORY")


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def build():
    plan = CONTROLS / "PLAN.json"
    cases = {row["uid"]: row for row in read(plan)["cases"]}
    excluded = HERE / "SELECTED_GEPA_EXPANSION_PANEL.json"
    old = read(excluded)["cases"]
    excluded_uids = {row["uid"] for row in old}
    excluded_groups = {cases[uid]["group_id"] for uid in excluded_uids}
    waves = sorted((CONTROLS / "waves").glob("[0-9][0-9].json"))
    endpoints = {}
    for path in waves:
        for row in read(path)["rows"]:
            if row["method"] not in METHODS or row["actor_status"] != "OK" or row["score"] is None:
                continue
            key = row["uid"], row["method"]
            if key in endpoints:
                raise ValueError(f"Duplicate archived endpoint: {key}")
            endpoints[key] = row
    pools = {"utility_opportunity": [], "misuse_opportunity": [], "passing_control": []}
    for uid, case in cases.items():
        group = case["group_id"]
        if uid in excluded_uids or group in excluded_groups or not all((uid, m) in endpoints for m in METHODS):
            continue
        if case["role"] != "DEV":
            raise ValueError(f"Unexpected cohort role: {case['role']}")
        category = case["category"]
        flag = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
        full, empty = (endpoints[uid, m] for m in METHODS)
        pair = full["score"][flag], empty["score"][flag]
        if category == "beneficial_memory_usage" and pair == (False, True):
            pools["utility_opportunity"].append(case)
        elif category != "beneficial_memory_usage" and pair == (True, False):
            pools["misuse_opportunity"].append(case)
        elif pair == (False, False):
            pools["passing_control"].append(case)
    selected, groups = [], set()
    for stratum, cap in (("misuse_opportunity", 4), ("utility_opportunity", 6), ("passing_control", 4)):
        pool = sorted(pools[stratum], key=lambda row: sha256(
            ("draft-conditioning-v1:" + row["uid"]).encode()).hexdigest())
        count = 0
        for case in pool:
            uid, group = case["uid"], case["group_id"]
            if group in groups:
                continue
            selected.append({"uid": uid, "group": group, "category": case["category"], "stratum": stratum,
                             "public_sha256": case["public_sha256"],
                             "actor_sha256": {m: endpoints[uid, m]["actor_request_sha256"] for m in METHODS}})
            groups.add(group)
            count += 1
            if count == cap:
                break
    counts = Counter(r["stratum"] for r in selected)
    if counts["misuse_opportunity"] < 2 or counts["utility_opportunity"] < 4:
        raise ValueError("Insufficient independent endpoint contrasts under frozen eligibility")
    inputs = {str(path.relative_to(HERE.parent)): digest(path) for path in [plan, excluded, *waves]}
    return {"cohort": "exposed development", "counts": dict(counts), "inputs": inputs, "rows": selected}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
