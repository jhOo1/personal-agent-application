"""Evaluate the cardinality branch using archived answers and original separate scorers."""
from collections import Counter
import json
from pathlib import Path

from cardinality import use_history
from qamc.common import sha

BASE = Path(__file__).resolve().parent.parent
OLD = BASE / "paper_baseline_validation_156_v1"
RUN = BASE.parents[1] / "runs" / BASE.name / "rpe_single_endpoint_bridge_v1"
FULL, ZERO = "RPR_PAPER_FULL", "TASK_ONLY"
EXTERNAL = (FULL, "DES2GEN_FULL", "MEMADAPTER_FULL")


def read(path):
    return json.loads(path.read_bytes())


def original_count(row):
    wire = row["actor_request"]
    if sha(wire) != row["actor_request_sha256"]:
        raise ValueError("Archived full-history wire drift")
    packet = json.loads(wire["messages"][1]["content"])
    source = packet["source_evidence"]
    ids = [r["memory_id"] for r in source]
    if len(ids) != len(set(ids)) or [r["memory_id"] for r in packet["preference_use_policy"]] != ids:
        raise ValueError("Source count differs from the original candidate inventory")
    return len(ids)


def single():
    selected = [r for r in read(OLD / "MANIFEST_156.json")
                if r["benchmark"] == "rpeval" and r["track"].endswith("/single")]
    if len(selected) != 24 or any(r["independent_confirmation"] for r in selected):
        raise ValueError("Expected the existing exposed single-preference roster")
    panel = {r["uid"] for r in selected}
    originals = {r["uid"]: r for r in read(OLD / "SAVED_OPPONENT_ROWS.json")
                 if r["uid"] in panel and r["method"] == FULL}
    rows = read(RUN / "RESULTS.json")["rows"]
    if len(rows) != len(panel) or set(originals) != set(panel) or {r["uid"] for r in rows} != set(panel):
        raise ValueError("An archived single-preference allocation is missing")
    counts = Counter()
    scores = {m: Counter() for m in ("cardinality", "IPE_C", *EXTERNAL)}
    by_label = {tag: Counter() for tag in "ABC"}
    for row in rows:
        count = original_count(originals[row["uid"]])
        if count != 1 or row["route"] not in (FULL, ZERO):
            raise ValueError("Unexpected baseline branch or source count")
        route = FULL if use_history(count, row["route"] == FULL) else ZERO
        counts["changed_route"] += row["route"] != route
        selected = row["scores"][route]
        values = {"cardinality": selected, **{name: row["scores"][name] for name in scores if name != "cardinality"}}
        if any(v is None for v in values.values()):
            counts["noncommon"] += 1
            continue
        counts["common"] += 1
        cmp = selected["matched"] - values["IPE_C"]["matched"]
        counts["win" if cmp > 0 else "loss" if cmp < 0 else "tie"] += 1
        for name, value in values.items():
            scores[name].update(match=value["matched"], **{k: value["severity"][k] for k in ("OPB", "UPB", "FM")})
        by_label[row["label"]].update(common=1, cardinality=selected["matched"], ipe_c=values["IPE_C"]["matched"])
    return {"assigned": len(rows), "counts": counts, "scores": scores, "label_strata": by_label,
            "scoring": "detailed author single-rubric with historical Qwen adaptation"}


def multi():
    endpoints = read(BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    originals = {r["uid"]: r for r in read(BASE / "rpeval_formal_multi_coverage_v1/RESULT_ROWS.json")
                 if r["method"] == FULL}
    counts = Counter()
    for row in endpoints:
        original = originals[row["uid"]]
        route = row["old_route"]
        if route == "ARCHIVED_ESTIMATE_OR_ACTOR_UNAVAILABLE" or original["actor_request"] is None:
            counts["unavailable"] += 1
            continue
        enabled = route == "REUSE_RP"
        count = original_count(original)
        if count <= 1 or use_history(count, enabled) != enabled:
            raise ValueError("The cardinality variant changed a multi-preference route")
        counts["identical_route"] += 1
        grade = row["ipe_c"]["grade"]
        match = grade.get("match") if grade else None
        if match and match["positions"] > 0:
            counts.update(grade_valid=1, match=match["matched"], positions=match["positions"])
    return {"assigned": len(endpoints), "counts": counts,
            "scoring": "separate detailed author multi-rubric with historical GPT-4.1 adaptation"}


if __name__ == "__main__":
    print(json.dumps({"single": single(), "multi": multi(), "new_requests": 0}, indent=2, sort_keys=True))
