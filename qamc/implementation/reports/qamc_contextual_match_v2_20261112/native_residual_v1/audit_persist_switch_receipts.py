"""Join saved PersistBench switch answers under identical evaluation envelopes."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SWITCH = "persist_switch_execution_v1"
SELECTED = "selected_rubric_exposure_v1"
GEPA = "selected_gepa_expansion_v1"
ENFORCED, ADVISORY = "ENFORCED_SWITCH", "ADVISORY_SWITCH"


def read(path):
    return json.loads(path.read_text())


def load(stage):
    place = HERE / stage
    rows = {(r["uid"], r["method"]): r for r in read(place / "RESULTS.json")["rows"]}
    requests = {}
    for item in read(place / "PersistNative_MANIFEST.json")["units"]:
        unit = item["unit"]
        method = unit["method"].removesuffix("/PersistJudge")
        key = unit["root_id"], method
        if key in requests or unit["replicate"] != 0:
            raise ValueError(f"Unexpected grading unit: {key}")
        requests[key] = item["request"]
    return rows, requests


def normalized(request, answer):
    wire = deepcopy(request)
    message = wire["messages"][-1]
    marker = f"<response>\n{answer}\n</response>"
    if message["role"] != "user" or message["content"].count(marker) != 1:
        raise ValueError("Archived answer cannot be identified exactly in Judge request")
    message["content"] = message["content"].replace(marker, "<response>\n{{ANSWER}}\n</response>")
    return wire


def audit():
    archives = {stage: load(stage) for stage in (SWITCH, SELECTED, GEPA)}
    counts, cases = Counter(), []
    for (uid, method), row in archives[SWITCH][0].items():
        if method != ENFORCED or row["mode"] != "OFF":
            continue
        mappings = {
            "enforced": (SWITCH, ENFORCED),
            "advisory": (SWITCH, ADVISORY),
            "selective_rubric": (SELECTED, "SELECTED_RUBRIC"),
            "full_with_selection": (SELECTED, "FULL_RUBRIC_WITH_SELECTION"),
            "selective_gepa": (GEPA, "SELECTED_GEPA"),
        }
        ratings, envelopes = {"archived_rubric": row["base_score"]["rating"]}, []
        for key, (stage, arm) in mappings.items():
            rows, requests = archives[stage]
            cell = rows[uid, arm]
            if cell["category"] != row["category"] or cell["base_score"] != row["base_score"]:
                raise ValueError(f"Baseline or track drift: {uid}/{arm}")
            score = cell["score"]
            ratings[key] = score["rating"] if score is not None else None
            if score is not None:
                envelopes.append(normalized(requests[uid, arm], cell["answer"]))
                counts["valid_score_request_envelopes"] += 1
        if not all(w == envelopes[0] for w in envelopes[1:]):
            raise ValueError(f"Different scoring envelope: {uid}")
        counts["off_roots"] += 1
        if ratings["advisory"] is not None:
            counts["matched_off"] += 1
            counts["equal_off_rating"] += ratings["enforced"] == ratings["advisory"]
        cases.append({"uid": uid, "category": row["category"], "ratings": ratings})
    return {"counts": counts, "cases": cases}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
