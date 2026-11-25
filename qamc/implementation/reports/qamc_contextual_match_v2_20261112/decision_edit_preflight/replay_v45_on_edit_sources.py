"""Replay already-settled native scores on the local-edit study's frozen source split."""
import json

from qamc.common import sha

import analyze_decision_witness_v45 as v45
import run_decision_edit as experiment


def replay():
    frozen_path = experiment.OUT / "FROZEN.json"
    settled_path = v45.run.OUT / "SETTLED.json"
    frozen = experiment.read(frozen_path)
    rows = experiment.read(settled_path)["rows"]
    eligible = [row for row in rows if row["assignment"] != "NO_USABLE_DRAFT"]
    reference = experiment.read(experiment.HERE / "PREFLIGHT.json")["RPEval"]["observed"]
    if {r["uid"] for r in reference} != {r["uid"] for r in eligible}:
        raise ValueError("Settled V45 and frozen local-edit eligible roots differ")
    mentioned = set(frozen["diagnostic_source_groups"])
    split = {"all": eligible,
             "outside_documented_diagnostics": [r for r in eligible if r["group"] not in mentioned],
             "within_documented_diagnostics": [r for r in eligible if r["group"] in mentioned]}
    if len(split["outside_documented_diagnostics"]) != frozen["eligible_outside_diagnostic_groups"]:
        raise ValueError("Frozen source split changed")
    comparisons = {}
    for split_name, panel in split.items():
        groups = {"all": panel,
                  "all_A": [r for r in panel if set(r["labels"]) == {"A"}],
                  "contains_BC": [r for r in panel if set(r["labels"]) != {"A"}]}
        comparisons[split_name] = {
            name: {
                method: {
                    "match": v45.run.stage.v42.paired(sample, method, v45.ANCHORED),
                    **{field: v45.archived.grade_pair(sample, method, v45.ANCHORED, field)
                       for field in ("OPB", "UPB", "FM", "full_match")},
                } for method in (v45.GENERIC, v45.RP, v45.GATE, v45.C_PRIOR)
            } for name, sample in groups.items()
        }
    return {
        "frozen_split_sha256": sha(frozen_path.read_bytes()),
        "population": {key: {"roots": len(value), "source_groups": len({r["group"] for r in value})}
                       for key, value in split.items()},
        "settled_v45_sha256": sha(settled_path.read_bytes()),
        "comparisons": comparisons,
        "new_model_calls": 0, "new_native_scores": 0,
        "independent_confirmation": False,
        "note": "The group split was frozen prospectively for local edit and is retrospective for V45. "
                "Previously exposed groups were highlighted for diagnostics and are not a randomized split.",
    }


if __name__ == "__main__":
    print(json.dumps(replay(), ensure_ascii=False, indent=2))
