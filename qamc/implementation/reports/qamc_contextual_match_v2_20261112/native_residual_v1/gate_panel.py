"""Select exposed, source-disjoint RPEval roots with complete Gate anchors."""
import argparse
from collections import Counter
import json

from build_jobs import archive_inputs
from freeze_roster import HERE
from qamc.common import sha
from scope_planner import inputs
from summarize_reassembly import measure
from trial_reassembly import archive, engine, probe

STRATA = ("all_A", "B_only", "contains_C")
QUOTA = {"all_A": 6, "B_only": 5, "contains_C": 6}


def build():
    wires, cards = archive_inputs()
    original_path = archive.v41.formal.OUT / "RESULT_ROWS.json"
    gate = {}
    for row in archive.read(original_path):
        if row["method"] != engine.GATE or row["actor_status"] != "OK":
            continue
        key = "RPEval", row["uid"]
        if key not in cards or not row.get("answer"):
            continue
        score = measure("RPEval", cards[key]["stratum"], row.get("native_fields"))
        if score is None or not row.get("raw_scores", {}).get(archive.v41.NATIVE):
            continue
        if key in gate:
            raise ValueError("Duplicate Gate anchor")
        gate[key] = row

    tatr = archive.read(HERE.parent / "transactional_reassembly_v1" / "FROZEN.json")
    excluded = {
        row["group"] for row in archive.read(HERE / "ROSTER.json")["rows"]
        if row["benchmark"] == "RPEval"
    }
    excluded.update(
        row["group"] for row in tatr["rows"]
        if row["benchmark"] == "RPEval" and row["diagnostic"]
    )
    eligible = {}
    rows = []
    for stratum in STRATA:
        keys = sorted(
            (key for key in gate.keys() & wires.keys() if cards[key]["stratum"] == stratum),
            key=lambda key: sha(["scope-gate-v1", cards[key]["group"], key[1]]),
        )
        seen = set()
        for key in keys:
            card, saved = cards[key], wires[key]
            group = card["group"]
            if group in excluded or group in seen:
                continue
            wire = saved["actor_request"]
            if sha(wire) != saved["actor_request_sha256"]:
                raise ValueError("Archived Actor hash mismatch")
            task, memory = inputs(wire, card["root"])
            if not task or not memory:
                continue
            seen.add(group)
            if len(seen) <= QUOTA[stratum]:
                rows.append({"uid": key[1], "group": group, "stratum": stratum,
                             "rpr_request_sha256": sha(wire),
                             "gate_answer_sha256": sha(gate[key]["answer"]),
                             "gate_grade_sha256": sha(gate[key]["native_fields"])})
        eligible[stratum] = len(seen)
        if len(seen) < QUOTA[stratum]:
            raise ValueError(f"Insufficient exposed groups for {stratum}: {len(seen)}")
        excluded.update(seen.intersection({r["group"] for r in rows}))
    return {"rows": rows, "eligible_groups": eligible}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check"))
    result = build()
    path = HERE / "GATE_PANEL.json"
    if parser.parse_args().action == "freeze":
        with path.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    elif probe.read(path) != result:
        raise ValueError("Panel drift")
    print(result["eligible_groups"], dict(Counter(r["stratum"] for r in result["rows"])))
