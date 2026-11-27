"""Find independent objective-expression profiles before the proposed BenchPreS intervention."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from qamc.common import sha
from qamc.pa.core import digest

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent.parent
PREVIOUS = BASE / "benchpres_repeat_matched_v1"
RUN = ROOT / "runs" / BASE.name / PREVIOUS.name
GATE = "GEPA_SELECTED_BOUNDS"
PRESPECIFIED_PURPOSES = {"appeal": "Appeal denied claim.",
                         "admissions": "Address academic performance variation."}


def read(p):
    return json.loads(p.read_text())


def attribute_kind(attribute):
    text = attribute.casefold()
    if "objective information provider" in text:
        return "objective_information"
    if "neutral perspective" in text:
        return "neutral_perspective"
    if re.search(r"\bneutral tone\b", text):
        return "neutral_tone"
    return None


def audit():
    plan = read(RUN / "PLAN_PRIVATE.json")
    pin = read(PREVIOUS / "PREFLIGHT.json")
    if sha(plan) != pin["plan_sha256"] or len(plan["cases"]) != 48:
        raise ValueError("Unexpected repeat comparison roster")
    attributes = {}
    groups = defaultdict(set)
    case_groups = {}
    group_tasks = defaultdict(set)
    stats = defaultdict(Counter)
    for case in plan["cases"]:
        if case["independent_confirmation"]:
            raise ValueError("Expected previously exposed cases")
        evaluation = read(ROOT / case["evaluation_path"])
        if digest(evaluation) != case["evaluation_hash"]:
            raise ValueError("Evaluation metadata binding changed")
        uid, group = case["uid"], case["analysis_group_id"]
        case_groups[uid] = group
        for index, (attribute, allowed) in enumerate(
            zip(evaluation["preference_attribute"], evaluation["preference_label"], strict=True)
        ):
            kind = attribute_kind(attribute)
            if kind is None or not allowed:
                continue
            attributes[uid, index] = attribute, kind
            groups[kind].add(group)
            group_tasks[kind].add(uid)
            stats[kind]["allocated_draw_attributes"] += 3
    seen = set()
    for wave in read(PREVIOUS / "FINAL_REPLAY.json")["settled_waves"]:
        for row in read(RUN / f"wave-{wave}" / "RESULTS.json"):
            uid = row["uid"]
            score = row["score"]
            if row["method"] != GATE or score is None:
                continue
            for index, verdict in enumerate(score["decisions"]):
                key = (uid, index)
                if key not in attributes:
                    continue
                identity = (*key, row["replicate"])
                if identity in seen:
                    raise ValueError("Duplicate draw attribute")
                seen.add(identity)
                expected, kind = attributes[key]
                if (verdict["preference"] != expected or not verdict["appropriate"]
                        or verdict["label"] not in ("follow", "do_not_follow")):
                    raise ValueError("Archived decision is not a valid bound label")
                stats[kind]["scored_draw_attributes"] += 1
                stats[kind]["follow"] += int(verdict["label"] == "follow")
    objective_tasks = group_tasks["objective_information"]
    objectives = {}
    for case in plan["cases"]:
        if case["uid"] not in objective_tasks:
            continue
        public = read(ROOT / case["public_path"])
        if digest(public) != case["public_hash"]:
            raise ValueError("Public case binding changed")
        first_line = public["query"].splitlines()[0]
        for name, purpose in PRESPECIFIED_PURPOSES.items():
            if first_line.endswith(f"purpose: {purpose}"):
                if name in objectives:
                    raise ValueError("Ambiguous pre-specified objective")
                objectives[name] = case_groups[case["uid"]]
    if objectives.keys() != PRESPECIFIED_PURPOSES.keys():
        raise ValueError("Could not recover both pre-specified tasks")
    return {"tasks": len(case_groups), "prespecified_examples_same_profile": len(set(objectives.values())) == 1,
            "attribute_family": {kind: {"distinct_tasks": len(group_tasks[kind]),
                                       "distinct_profiles": len(groups[kind]), **stats[kind]}
                                 for kind in sorted(groups)},
            "admitted_objectivity_profile_count": len(groups.get("objective_information", set())),
            "objective_and_neutral_perspective_profiles_overlap": len(
                groups["objective_information"] & groups["neutral_perspective"]
            ),
            "model_calls": 0, "original_grades_replaced": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
