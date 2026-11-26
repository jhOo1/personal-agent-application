"""Freeze a score-blind-by-inclusion panel with saved external controls."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent
CONTROLS = REPORTS / "persist_author_controls_v2"


def read(path):
    return json.loads(path.read_text())


def build():
    plan = CONTROLS / "PLAN.json"
    old_files = [
        HERE / "SELECTED_GEPA_EXPANSION_PANEL.json",
        HERE / "DRAFT_CONDITIONING_PANEL.json",
        REPORTS.parent / "qamc_persistbench_grounding_transfer" / "PLAN.json",
    ]
    old_uids = set()
    for path in old_files:
        old = read(path)
        old_uids.update(row["uid"] for row in old.get("cases", old.get("rows", [])))
    controls = read(plan)
    if controls["not_confirmation"] is not True:
        raise ValueError("Expected an exposed development cohort")
    cases = controls["cases"]
    old_groups = {row["group_id"] for row in cases if row["uid"] in old_uids}
    rubric = {}
    waves = sorted((CONTROLS / "waves").glob("[0-9][0-9].json"))
    for path in waves:
        for row in read(path)["rows"]:
            if row["method"] == "PB_RUBRIC" and row["actor_status"] == "OK" and row["score"] is not None:
                if row["uid"] in rubric:
                    raise ValueError(f"Duplicate reference: {row['uid']}")
                rubric[row["uid"]] = row
    rows, groups = [], set()
    for case in sorted(cases, key=lambda row: sha256(
            ("persist-performance-v1:" + row["uid"]).encode()).hexdigest()):
        uid, group = case["uid"], case["group_id"]
        if uid in old_uids or group in old_groups or group in groups or uid not in rubric:
            continue
        if case["role"] != "DEV":
            raise ValueError(f"Unexpected role: {case['role']}")
        row = rubric[uid]
        rows.append({"uid": uid, "group": group, "line": case["line"], "category": case["category"],
                     "public_sha256": case["public_sha256"], "actor_request_sha256": row["actor_request_sha256"],
                     "answer_sha256": sha256(row["answer"].encode()).hexdigest(), "score": row["score"]})
        groups.add(group)
    inputs = {str(path.relative_to(REPORTS.parent)): sha256(path.read_bytes()).hexdigest()
              for path in [plan, *old_files, *waves]}
    return {"cohort": "already exposed development, disjoint by recorded group from named pilots",
            "counts": dict(Counter(row["category"] for row in rows)), "inputs": inputs, "cases": rows}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
