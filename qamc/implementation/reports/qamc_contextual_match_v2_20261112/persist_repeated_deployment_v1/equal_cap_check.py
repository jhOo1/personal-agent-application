"""Verify the separately archived same-cap GEPA exposure comparison."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path


def audit():
    api = run_path(str(Path(__file__).with_name("run.py")))
    transfer = api["transfer"]
    factorial = transfer.ROOT / "reports/qamc_persistbench_actor_factorial"
    read = api["read"]
    plan = read(factorial / "PLAN.json")
    previous = read(transfer.OUT / "PLAN.json")
    results = read(factorial / "PILOT.json")["rows"]
    rows = {(r["uid"], r["method"]): r for r in results}
    if len(rows) != len(results):
        raise ValueError("Duplicate historical result")
    graders = {}
    for origin, stage_arm, method in ((factorial, "SELECTED_GEPA", "SELECTED_GEPA"),
                                      (transfer.OUT, "GEPA", "FULL_GEPA")):
        manifest = read(origin / "stage_manifests/pilot_Judges.json")
        for cell in manifest["units"]:
            unit = cell["unit"]
            if unit["method"] == stage_arm:
                graders[unit["root_id"], method] = cell["request"]
    source = transfer.smoke.source()
    totals = {}
    for case in plan["cases"]:
        uid, category = case["uid"], case["category"]
        task = transfer.smoke.public(source[case["line"] - 1])
        if api["sha"](task) != case["public_sha256"]:
            raise ValueError("Historical task bytes changed")
        observed = {"SELECTED_GEPA": plan["jobs"][uid]["SELECTED_GEPA"]["request"],
                    "FULL_GEPA": previous["jobs"][uid]["gepa"]["request"]}
        exposures = {"SELECTED_GEPA": plan["evidence"][uid], "FULL_GEPA": task["memories"]}
        if any(w["max_tokens"] != 8192 for w in observed.values()):
            raise ValueError("Archived generation cap mismatch")
        envelopes, outcomes = [], []
        for method, wire in observed.items():
            expected = api["actor_request"](case, task["query"], exposures[method], plan, plan["prompts"]["gepa"])
            row = rows[uid, method]
            if wire != expected or api["sha"](wire) != row["actor_request_sha256"]:
                raise ValueError("Stored generator does not match the GEPA exposure reconstruction")
            envelopes.append(api["normalized"](graders[uid, method], row["answer"]))
            outcomes.append(api["passes"](row["score"], category))
        if envelopes[0] != envelopes[1]:
            raise ValueError("Within-task grader differs beyond the answer")
        candidate, reference = outcomes
        for key in (category, "all"):
            totals.setdefault(key, Counter()).update(common=1, selected_pass=candidate, full_pass=reference,
                                                    wins=candidate and not reference,
                                                    losses=reference and not candidate)
    return totals


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
