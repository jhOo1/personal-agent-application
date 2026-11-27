"""Audit settled repairs locally. Keep row-level inputs and score reasons private."""
from collections import Counter
from difflib import SequenceMatcher
import json

from protected import apply, decode, default_answer, locate
from qamc.common import sha
from repair_trial import ARMS, RUN, assign
from run_bridge import probe, read


def outcome(score):
    return None if score is None else int(score["matched"])


def project_locator(raw, packet):
    """Diagnose the one extra-field error while discarding unsolicited edits."""
    parsed = decode(raw)
    targets = parsed.get("targets")
    if not isinstance(targets, list) or not targets:
        return None
    sanitized, removed = [], 0
    for target in targets:
        if not isinstance(target, dict):
            return None
        if set(target) == {"op", "quote", "replacement"} and isinstance(target["replacement"], str):
            removed += 1
        elif set(target) != {"op", "quote"}:
            return None
        sanitized.append({name: target[name] for name in ("op", "quote")})
    if not removed:
        return None
    try:
        return locate(json.dumps({**parsed, "targets": sanitized}, ensure_ascii=False), packet)
    except (ValueError, TypeError, KeyError):
        return None


def match_delta_bounds(rows, left, right):
    """Worst and best net Match over the assigned panel, keeping observed outcomes fixed."""
    low = high = 0
    for row in rows:
        a, b = (outcome(row["grade"][method]) for method in (left, right))
        low += (0 if a is None else a) - (1 if b is None else b)
        high += (1 if a is None else a) - (0 if b is None else b)
    return [low, high]


def main():
    packets, binding, _, _, pin = assign()
    if read(RUN / "FROZEN.json") != pin:
        raise ValueError("Frozen source binding changed")
    diagnoses = read(RUN / "DIAGNOSES.json")
    delivered = read(RUN / "LOCKED_ANSWERS.json")
    scored = read(RUN / "SCORED_ROWS.json")
    if not (packets.keys() == diagnoses.keys() == delivered.keys() == scored.keys()):
        raise ValueError("Incomplete audit inventory")
    aggregate = {
        "locator": Counter(row["state"] for row in diagnoses.values()),
        "locator_contract_errors": Counter(row["error"] for row in diagnoses.values() if row["error"]),
        "target_ops": Counter(target["op"] for row in diagnoses.values()
                              for target in (row["diagnosis"] or {}).get("targets", [])),
        "intervention_counts": {arm: Counter() for arm in ARMS},
        "misses_and_repairs": {arm: Counter() for arm in ARMS},
        "structurally_recoverable_locator_extras": 0,
        "match_delta_bounds_22": {}, "match_delta_bounds_24": {},
    }
    manifest = {}
    for key, packet in packets.items():
        source, score = diagnoses[key], scored[key]
        original = default_answer(packet)
        if source["state"] == "ACT" and locate(source["receipt"]["answer"], packet) != source["diagnosis"]:
            raise ValueError("Locked diagnosis cannot be reproduced")
        grades = {name: outcome(value) for name, value in score["grade"].items()}
        row = {"uid": binding[key]["uid"], "label": score["label"], "locator": source["state"],
               "matches": grades, "repair": {}}
        if source["error"] == "invalid target operation":
            projected = project_locator(source["receipt"]["answer"], packet)
            if projected is not None:
                row["offline_projection"] = projected
                aggregate["structurally_recoverable_locator_extras"] += 1
        for arm in ARMS:
            final = delivered[key][arm]
            answer = final["answer"]
            actual_digest = sha(answer) if answer is not None else None
            if actual_digest != score[arm]["answer_sha256"]:
                raise ValueError("Locked answer and score binding disagree")
            state, changed = final["status"], answer is not None and answer != original
            aligned = None
            if changed:
                aligned = sum(chunk.size for chunk in SequenceMatcher(None, original, answer, autojunk=False)
                              .get_matching_blocks())
                check = apply(final["receipt"]["answer"], packet, source["diagnosis"], arm)
                if answer != check:
                    raise ValueError("Committed edit cannot be reproduced")
                kind = "ARCHIVED_CANDIDATE" if answer in packet["candidates"].values() else "NEW_CANDIDATE"
                aggregate["intervention_counts"][arm][kind] += 1
            row["repair"][arm] = {"status": state, "changed": changed, "chars_aligned": aligned,
                                  "original_chars": len(original), "final_chars": len(answer) if answer else None,
                                  "judge_status": score[arm]["score_status"]}
            a, b = grades[arm], grades["RP"]
            outcome_label = "MISSING" if a is None else "RECOVERY" if a > b else "REGRESSION" if a < b else "TIE"
            aggregate["misses_and_repairs"][arm][f"{source['state']}:{outcome_label}"] += 1
        manifest[key] = row
    for other in ("RP", "V1", "FREE", "MemAdapter"):
        pair = f"PATCH_vs_{other}"
        aggregate["match_delta_bounds_22"][pair] = match_delta_bounds(
            [r for r in scored.values() if r["historical"]], "PATCH", other)
        aggregate["match_delta_bounds_24"][pair] = match_delta_bounds(scored.values(), "PATCH", other)
    probe.freeze(RUN / "AUDIT.json", aggregate)
    probe.freeze(RUN / "AUDIT_ROWS_PRIVATE.json", manifest)
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
