"""Test a guarded answer switch on frozen V45 witnesses and native grades."""
from collections import Counter
import json

from qamc.common import sha

import analyze_decision_witness_v45 as archive
from decision_witness_v45 import check, parse, task_text


run = archive.run
RP, ZERO = archive.RP, archive.ZERO
WITNESS, PRIOR = archive.ANCHORED, archive.C_PRIOR
GUARDED = "GUARDED_RP"
OTHER = (RP, ZERO, WITNESS, PRIOR, archive.GENERIC, archive.GATE)
REASONS_TO_SWITCH = {"MISAPPLIED_MEMORY", "TASK_REQUIREMENT", "SOFT_VALUE", "FIRM_MEMORY"}
VETO_KINDS = {"TASK_REQUIREMENT", "FIRM_MEMORY", "SOFT_VALUE"}


def guarded_switch(packet, records):
    sides = {item["id"]: item["generation_context"] for item in packet["candidates"]}
    supported = {RP: [], ZERO: []}
    for record in records:
        source = RP if sides[record["side"]] == "SOURCE_RP" else ZERO
        supported[source].append(record["kind"])
    repair = REASONS_TO_SWITCH.intersection(supported[ZERO])
    veto = VETO_KINDS.intersection(supported[RP])
    if repair and not veto:
        return ZERO, "REPAIR_WITHOUT_OBSERVED_REGRESSION", supported
    return RP, "PROTECTED_RP_VALUE" if repair else "NO_WITNESSED_REPAIR", supported


def evidence(packet, raw):
    candidates = {item["id"]: item for item in packet["candidates"]}
    sources = {item["memory_id"]: item["text"] for item in packet["source_evidence"]}
    task = tuple(task_text(packet["task"]))
    return [item for item in parse(raw) if check(item, candidates, sources, task) is None]


def replay():
    # The terminal V45 artifact was previously verified by replay from physical receipts.
    plan, manifest, alias_list = run.artifacts()
    state = run.read(run.OUT / "RUN_STATE.json")
    saved_path = run.OUT / "SETTLED.json"
    saved = run.read(saved_path)
    if state["state"] != "COMPLETE" or len(saved["ledger"]) != plan["witness_request_cap"]:
        raise ValueError("V45 has not settled")
    wire_map = {item["unit"]["root_id"]: item["request"] for item in manifest["units"]}
    for alias in alias_list:
        wire_map[alias["uid"]] = wire_map[alias["physical_uid"]]
    hashed = {row["request_sha256"]: row for row in saved["ledger"]}
    if len(hashed) != len(saved["ledger"]):
        raise ValueError("Duplicate physical witness requests")

    rows, decisions = saved["rows"], []
    for row in rows:
        uid = row["uid"]
        witness = row["witness"]
        if witness["status"] == "COMPILED":
            wire = wire_map[uid]
            if hashed[sha(wire)]["status"] != "OK":
                raise ValueError("Compiled witness has no successful physical receipt")
            packet = json.loads(wire["messages"][1]["content"])
            accepted = evidence(packet, witness["raw"])
            if len({sha(item) for item in accepted}) != witness["accepted"]:
                raise ValueError("Anchored evidence differs from V45")
            chosen, reason, supported = guarded_switch(packet, accepted)
        else:
            chosen, reason, supported = RP, "NO_VALID_WITNESS", {}
        row["native"][GUARDED] = {**row["native"][chosen], "reuse": chosen}
        decisions.append({"uid": uid, "group": row["group"], "choice": chosen,
                          "reason": reason, "witnessed_kinds": supported})
    eligible = [row for row in rows if row["assignment"] != "NO_USABLE_DRAFT"]
    cohorts = {
        "assigned": rows, "eligible": eligible,
        "all_A": [row for row in eligible if set(row["labels"]) == {"A"}],
        "B_only": [row for row in eligible if "B" in row["labels"] and "C" not in row["labels"]],
        "has_C": [row for row in eligible if "C" in row["labels"]],
        "less_exposed": [row for row in eligible if row["less_exposed"]],
    }
    paired = {}
    for key, cohort in cohorts.items():
        paired[key] = {}
        for comparator in OTHER:
            match = run.stage.v42.paired(cohort, comparator, GUARDED)
            common = set(match["valid_uids"])
            matched = [row for row in cohort if row["uid"] in common]
            paired[key][comparator] = {
                "match": match,
                **{field: archive.archived.grade_pair(matched, comparator, GUARDED, field)
                   for field in ("OPB", "UPB", "FM", "VG", "full_match")},
            }
    thresholds = plan["thresholds"]
    checks = {}
    for comp in (RP, PRIOR):
        main = paired["eligible"][comp]["match"]
        checks[comp] = {
            "coverage": main["valid_cases"] >= thresholds["coverage"] * len(eligible),
            "positive_match_interval": main.get("95pct_source_bootstrap", [-1])[0] > 0,
        }
        for cohort in ("B_only", "has_C"):
            section = paired[cohort][comp]
            bound = thresholds["contains_BC_match_noninferiority_margin"]
            harm = thresholds["contains_BC_UPB_and_FM_harm_margin_per_answer"]
            checks[comp][cohort] = (
                section["match"]["valid_cases"] >= thresholds["coverage"] * len(cohorts[cohort])
                and section["match"].get("95pct_source_bootstrap", [-1])[0] >= -bound
                and all(section[field]["n"] >= thresholds["coverage"] * len(cohorts[cohort])
                        and section[field].get("95pct_source_bootstrap", [0, 1])[1] <= harm
                        for field in ("UPB", "FM")))
    return {"artifacts": {"v45_sha256": sha(saved_path.read_bytes()), "manifest_sha256": sha(manifest)},
            "physical_requests": 0, "eligible": len(eligible), "assigned": len(rows),
            "decisions": decisions, "reasons": Counter(item["reason"] for item in decisions),
            "paired": paired, "diagnostic_checks": checks,
            "passed": all(all(values.values()) for values in checks.values())}


if __name__ == "__main__":
    print(json.dumps(replay(), ensure_ascii=False, indent=2))
