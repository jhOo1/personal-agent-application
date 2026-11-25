"""Trace legal preference positions through existing proposals, admission, and prose links."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_linked_decision_render as run


def source_id(value):
    return value.get("id") if isinstance(value, dict) else None


def proposal_stages(root, blocks, raw):
    rank = run.method.rank
    decisions = rank.model_object(raw, "decisions")["decisions"]
    if not isinstance(decisions, list):
        raise ValueError("Archived decision proposal has no decision list")
    evidence = {item["memory_id"]: item for item in root["original_sources"]}
    proposed = defaultdict(list)
    for row in decisions:
        if not isinstance(row, dict) or not isinstance(row.get("block"), str):
            continue
        slot = row["block"]
        block = blocks.get(slot, {})
        guard = row.get("guard")
        if isinstance(guard, dict) and isinstance(guard.get("sources"), list):
            options = {f"O{i}" for i in range(1, len(block.get("lines", ())) + 1)}
            affected = block.get("affected")
            audience = guard.get("audience")
            allowed = {"SELF": ("SELF",), "PARTICIPANT": ("SHARED",), "GROUP": ("SHARED", "OTHER")}
            for cite in guard["sources"]:
                mid = source_id(cite)
                if not isinstance(mid, str) or mid not in evidence:
                    continue
                grounded = rank.grounded(cite, evidence)
                if not grounded:
                    stage = "SOURCE_QUOTE_REJECTED"
                elif block.get("kind") != "CHOICE":
                    stage = "NO_CHOICE_BLOCK"
                elif len(guard["sources"]) > 4:
                    stage = "BUNDLED_SOURCE_LIMIT"
                elif affected not in (allowed.get(audience, ()) if isinstance(audience, str) else ()):
                    stage = "BUNDLED_ROLE_MISMATCH"
                elif not rank.valid_guard(guard, affected, options, evidence):
                    stage = "BUNDLED_GUARD_INVALID"
                else:
                    stage = "VALID_GUARD_PROPOSAL"
                proposed[mid].append({"slot": slot, "stage": stage, "quote": cite.get("quote"),
                                      "guard_audience": audience, "block_affected": affected})
        preferences = row.get("preferences")
        if isinstance(preferences, list):
            for pref in preferences:
                if isinstance(pref, dict):
                    cite = pref.get("source")
                    mid = source_id(cite)
                    if isinstance(mid, str) and mid in evidence:
                        proposed[mid].append({"slot": slot, "stage": "SOFT_PROPOSAL", "quote": cite.get("quote")})
    return proposed


def trace(row, root, blocks):
    previous = row["attempts"].get(run.method.OFF, {})
    if run.method.ON not in row["outputs"]:
        return None
    proposals = proposal_stages(root, blocks, previous["raw"])
    accepted, linked = set(), set()
    for slot, policy in row["policy"].items():
        if not policy["guard"]:
            continue
        ids = {cite["id"] for cite in policy["guard"]["sources"]}
        accepted.update(ids)
        if any(edit["choice"] == slot for edits in row["links"].values() for edit in edits):
            linked.update(ids)
    soft = {pref["source"]["id"] for policy in row["policy"].values() for pref in policy["preferences"]}
    compiled = []
    for source, label in zip(root["original_sources"], row["labels"], strict=True):
        mid = source["memory_id"]
        raw = proposals[mid]
        guards = [record for record in raw if record["stage"] != "SOFT_PROPOSAL"]
        stage = ("GUARD_LINKED" if mid in linked else "GUARD_ACCEPTED" if mid in accepted else
                 "GUARD_PROPOSED_REJECTED" if guards else "SOFT_ACCEPTED" if mid in soft else
                 "SOFT_PROPOSED_REJECTED" if raw else "NOT_PROPOSED")
        compiled.append({"source_id": mid, "label": label, "stage": stage, "raw_proposals": raw})
    return compiled


def audit():
    _, _, source, roots, _ = run.prepare()
    settled = run.OUT / "SETTLED.json"
    rows = run.read(settled)["rows"]
    grouped = Counter()
    by_lane = Counter()
    cases = []
    for row in rows:
        uid = row["uid"]
        side = "primary" if row["primary"] else "regression"
        result = trace(row, roots[uid], source[uid]["execution"]["blocks"])
        grouped[side, "cases_available" if result is not None else "cases_unavailable"] += 1
        for slot in result or []:
            by_lane[side, slot["label"], slot["stage"]] += 1
        cases.append({"uid": uid, "group": row["group"], "side": side, "positions": result,
                      "compose_status": row["attempts"].get(run.method.OFF, {}).get("status")})
    return {"settled_sha256": sha(settled.read_bytes()), "model_requests": 0,
            "labels_used_only_for_diagnostic_reporting": True,
            "case_coverage": [{"side": side, "key": key, "count": count} for (side, key), count in sorted(grouped.items())],
            "positions": [{"side": side, "label": label, "stage": stage, "count": count}
                          for (side, label, stage), count in sorted(by_lane.items())],
            "cases": cases}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
