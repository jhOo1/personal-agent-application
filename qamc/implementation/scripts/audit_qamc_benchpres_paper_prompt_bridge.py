"""Retain attribute coverage independently of BenchPreS completeness parsing."""
from collections import Counter
import json
import re

import run_qamc_benchpres_paper_prompt_bridge as trial
from qamc.common import parse_object

NICKNAME = re.compile(r'\bprefers? to be called ["“]([^"”]+)["”]', re.I)
ATTRIBUTES = tuple(f"BenchAttr{i}" for i in range(5))
METHODS = ("STYLE", "GP0", trial.METHOD)


def attribute_labels(row):
    raws = row.get("judge_answers", {})
    if any(stage not in raws for stage in ATTRIBUTES):
        return None
    try:
        labels = [parse_object(raws[stage]).get("label") for stage in ATTRIBUTES]
    except ValueError:
        return None
    return labels if all(label in ("follow", "do_not_follow") for label in labels) else None


def main():
    plan = trial.read(trial.OUT / "PLAN.json")
    trial.check(plan)
    old = trial.read(trial.previous.OUT / "PILOT.json")["rows"]
    new = trial.read(trial.OUT / "PILOT.json")["rows"]
    by = {(r["uid"], r["method"]): r for r in old if r["method"] in METHODS}
    by.update({(r["uid"], trial.METHOD): r for r in new})
    counts = {method: Counter() for method in METHODS}
    cases, missing, nickname_checks = [], [], []
    for c in plan["cases"]:
        uid = c["uid"]
        rows = {m: by[uid, m] for m in METHODS}
        labels = {m: attribute_labels(r) for m, r in rows.items()}
        if any(value is None for value in labels.values()):
            missing.append({"uid": uid, "arms": [m for m, v in labels.items() if v is None]})
            continue
        ref = trial.read(trial.ROOT / c["evaluation_path"])
        assert trial.bench.digest(ref) == c["evaluation_hash"]
        case = {m: Counter() for m in METHODS}
        for index, (attribute, appropriate) in enumerate(zip(
            ref["preference_attribute"], ref["preference_label"], strict=True
        )):
            kind = "bold" if re.search(r"\bbold text\b", attribute, re.I) else "other"
            for m, prediction in labels.items():
                followed = prediction[index] == "follow"
                prefix = "aar" if appropriate else "mr"
                case[m][f"{prefix}_n"] += followed
                case[m][f"{prefix}_d"] += 1
                if appropriate:
                    case[m][f"{kind}_n"] += followed
                    case[m][f"{kind}_d"] += 1
                else:
                    match = NICKNAME.search(attribute)
                    subtype = "nickname" if match else "other_mr"
                    case[m][f"{subtype}_n"] += followed
                    case[m][f"{subtype}_d"] += 1
                    if match:
                        nickname = match.group(1)
                        present = bool(re.search(rf"(?<!\w){re.escape(nickname)}(?!\w)", rows[m]["answer"]))
                        nickname_checks.append({"uid": uid, "method": m, "nickname": nickname,
                                                "label": prediction[index], "word_boundary_presence": present})
        for m, cell in case.items():
            counts[m].update(cell)
            if score := rows[m]["score"]:
                assert cell["aar_n"] == score["aar_numerator"] and cell["mr_n"] == score["mr_numerator"]
        cases.append({"uid": uid, "profile_group": c["profile_group"], "counts": case,
                      "missing_complete_score": [m for m, r in rows.items() if r["score"] is None]})
    print(json.dumps({"counts": counts, "cases": cases, "missing": missing, "nickname_checks": nickname_checks, "model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
