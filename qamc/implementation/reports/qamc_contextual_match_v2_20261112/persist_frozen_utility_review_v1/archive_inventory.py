"""Verify exposure and generation contracts for the historical utility pairs."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

from qamc.common import sha

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
BU = "beneficial_memory_usage"


def indexed(path, method, eligible):
    records = {}
    for row in json.loads(path.read_text())["units"]:
        unit = row["unit"]
        uid = unit["root_id"]
        if uid in eligible and unit["method"] == method:
            if uid in records:
                raise ValueError("Duplicate historical request for the same task")
            records[uid] = row["request"]
    return records


def audit():
    archive = run_path(str(BASE / "persist_author_score_bridge_v1/check.py"))
    latest = run_path(str(BASE / "persist_equal_cap_development_v1/run_bu.py"))
    pin, api, _, _, _, factorial, *_ = latest["prepare"]()
    if pin != latest["read"](latest["RUN"] / "FROZEN.json"):
        raise ValueError("Newer utility cohort changed")
    selected, controls, rows, cases = archive["checked_answers"]()
    method, full = archive["ACTIVE"], "PB_GEPA"
    eligible = {uid for uid, (category, _) in selected.items()
                if category == BU and full in controls[uid]}
    if len(eligible) != 18 or len({cases[u]["group_id"] for u in eligible}) != 18:
        raise ValueError("Unexpected historical utility cohort")
    buckets = (BASE / "native_residual_v1/selected_gepa_expansion_v1",
               BASE / "native_residual_v1/persist_performance_v1", archive["RUN"])
    actor, route, selector = {}, {}, {}
    for bucket in buckets:
        for field, table in (("FinalActor", actor), ("QueryRoute", route), ("EvidenceSelect", selector)):
            records = indexed(bucket / f"{field}_MANIFEST.json", method, eligible)
            if table.keys() & records.keys():
                raise ValueError("Historical stages overlap")
            table.update(records)
    prior_plan = latest["read"](ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    transfer_plan = latest["read"](api["transfer"].OUT / "PLAN.json")
    counters = Counter()
    for uid in sorted(eligible):
        case = cases[uid]
        task = api["persist"].author.parent.smoke.task_for(case)
        public = {"query": task.query, "memories": [m.text for m in task.memories]}
        if sha(public) != case["public_sha256"]:
            raise ValueError("Archived underlying task changed")
        full_wire = rows[uid, full]["actor_request"]
        if sha(full_wire) != rows[uid, full]["actor_request_sha256"]:
            raise ValueError("Full answer request changed")
        new_full = api["actor_request"](case, task.query, public["memories"], factorial,
                                       factorial["prompts"]["gepa"])
        if actor.get(uid) is None:
            selected_wire = prior_plan["jobs"][uid][method]["request"]
            if sha(selected_wire) != rows[uid, method]["actor_request_sha256"]:
                raise ValueError("Selected archive request hash changed")
            counters["historical_factorial"] += 1
        else:
            selected_wire = actor[uid]
            expected = api["input_requests"](case, public, transfer_plan)
            if route[uid] != expected["query"] or selector[uid] not in (
                    expected["style"], expected["grounding"]):
                raise ValueError("Archived route or selector wire differs from the current contract")
            counters["identical_route_and_selector_request_contract"] += 1
        old_score = selected[uid][1]
        if rows[uid, method]["score"] != old_score or rows[uid, full]["score"] != controls[uid][full]:
            raise ValueError("Historical scores differ from bound records")
        counters[f"actor_caps/{selected_wire['max_tokens']}/{full_wire['max_tokens']}"] += 1
        different_settings = [k for k in selected_wire.keys() | new_full.keys()
                              if k != "messages" and selected_wire.get(k) != new_full.get(k)]
        if not different_settings and selected_wire["messages"][1:] == new_full["messages"][1:]:
            counters["same_selected_actor_non_evidence_settings_as_current"] += 1
        if full_wire == dict(new_full, max_tokens=full_wire["max_tokens"]):
            counters["archived_full_matches_current_except_cap"] += 1
        selected_pass = api["passes"](old_score, BU)
        full_pass = api["passes"](controls[uid][full], BU)
        counters["selected_strict_pass"] += selected_pass
        counters["full_strict_pass"] += full_pass
        counters["both_strict_pass"] += selected_pass and full_pass
    rows_current = latest["read"](latest["RUN"] / "RESULTS.json")["rows"]
    ready = {arm: {r["uid"] for r in rows_current if r["arm"] == arm and r["score"] is not None}
             for arm in ("ROUTED", "FULL")}
    return {"historical_pairs": len(eligible), "groups": len({cases[u]["group_id"] for u in eligible}),
            "uid_overlap_current_plan": len(eligible & pin["cohort"].keys()),
            "uid_overlap_current_complete_pairs": len(eligible & ready["ROUTED"] & ready["FULL"]),
            "contract_checks": counters, "external_requests": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
