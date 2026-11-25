"""Find explicit target-intent contradictions in preserved RPEval reasoning summaries."""
from argparse import ArgumentParser
from collections import Counter
import json
import re

from qamc.common import sha

import run_decision_transactions as run


TARGET = r"(?:(?<![A-Za-z_])intent(?:_type)?(?![A-Za-z_])|(?:用户)?真实意图|目标意图)"
DIGITS = r"\d+(?:\s*[、，,和及与]\s*\d+)*"
LABEL_STRING = re.compile(TARGET + r"\s*(?:为|是|[:：=]|等于)\s*[\"“『「'\x60]?([ABC]{2,})(?![A-Za-z])",
                          re.IGNORECASE)
POSITION_CLAIM = r"第\s*(" + DIGITS + r")\s*(?:条|项|位)\s*(?:应为|应是|为|是)\s*([ABC])(?![A-Za-z])"
CLAIM = re.compile(POSITION_CLAIM, re.IGNORECASE)
TARGET_LIST = re.compile(TARGET + r"\s*(?:明确)?(?:要求|规定|指定)\s*[:：，,]?\s*(" + POSITION_CLAIM
                         + r"(?:\s*(?:[（(][^）)]{0,20}[）)])?\s*[,，、；;]\s*(?:" + POSITION_CLAIM + r"))*)",
                         re.IGNORECASE)
CANONICAL_INTENT = re.compile(r"^【intent】：([ABC]+)\s*$", re.MULTILINE)
CANONICAL_INTENT_TYPE = re.compile(r"^【intent_type】：([ABC]+)\s*$", re.MULTILINE)


def explicit_target_claims(reason, positions):
    """Only recognize positive statements explicitly attributed to the target."""
    claims = []
    for match in LABEL_STRING.finditer(reason):
        text = match.group(1).upper()
        if len(text) == positions:
            claims.append({"quote": match.group(0), "labels": {i: label for i, label in enumerate(text, 1)}})
    for match in TARGET_LIST.finditer(reason):
        excerpt = match.group(1)
        observed = {}
        for point in CLAIM.finditer(excerpt):
            for number in re.findall(r"\d+", point.group(1)):
                position = int(number)
                if not 1 <= position <= positions:
                    continue
                observed.setdefault(position, set()).add(point.group(2).upper())
        unique = {i: next(iter(values)) for i, values in observed.items() if len(values) == 1}
        if unique:
            claims.append({"quote": match.group(0), "labels": unique})
    return claims


def flagged_match_bounds(rows, treatment, control, flagged):
    """Replace only flagged aggregate scores by their full admissible range."""
    observed, known, total = 0, 0, 0
    contributions, widths = Counter(), {}
    for row in rows:
        total += row["positions"]
        for arm, direction in ((treatment, 1), (control, -1)):
            cell = row["native"][arm]
            matched = cell["fields"]["match"]["matched"]
            observed += direction * matched
            digest = cell["request_sha256"]
            if digest not in flagged:
                known += direction * matched
                continue
            if widths.setdefault(digest, row["positions"]) != row["positions"]:
                raise ValueError("An exact judge request has different Match denominators")
            contributions[digest] += direction
    # An identical receipt on both sides is a single unknown and cancels.
    possible = [direction * widths[digest] for digest, direction in contributions.items()]
    bounds = [known + sum(min(0, x) for x in possible), known + sum(max(0, x) for x in possible)]
    if not bounds[0] <= observed <= bounds[1]:
        raise ValueError("Rebuilt Match bounds exclude the observed value")
    return {"paired_histories": len(rows), "positions": total, "observed_match_difference": observed,
            "range_replacing_flagged_only": bounds, "same_wire_cancellations": sum(value == 0 for value in contributions.values())}


def audit(settled):
    method = run.method
    rows = {row["uid"]: row for row in settled["rows"]}
    unique = {}
    inspected = Counter()

    scorer = run.previous.prior.old.prior.parent.prior.parent.joint.parent

    def check_score_wires(_, jobs):
        result = {}
        for uid, arm, wire in jobs:
            row, digest = rows[uid], sha(wire)
            cell = row["native"][arm]
            if cell["request_sha256"] != digest:
                raise ValueError(f"Native score request changed for {uid}/{arm}")
            user_text = wire["messages"][1]["content"]
            expected = row["labels"]
            if ([expected] != CANONICAL_INTENT.findall(user_text)
                    or [expected] != CANONICAL_INTENT_TYPE.findall(user_text)):
                raise ValueError(f"Declared target absent from the expected native score wire for {uid}")
            body = cell.get("raw")
            if cell["status"] == "OK" and isinstance(body, str):
                score = scorer.parse_object(body)
                reason = score.get("reason", "")
                if isinstance(reason, str):
                    candidate = unique.setdefault(digest, {"target": expected, "locations": [], "reason": reason})
                    if (candidate["target"], candidate["reason"]) != (expected, reason):
                        raise ValueError("One exact judge request has inconsistent archived reasons")
                    candidate["locations"].append({"uid": uid, "method": arm})
            inspected[f"{arm}/{cell['status']}"] += 1
            result[uid, arm] = ({"status": cell["status"], "request_sha256": digest}, body)
        return result

    # Rebuild the actual Author-style judge request from each scored answer.
    # The dispatcher is a local callback and never uses the gateway.
    run.grade({uid: {**row, "native": dict(row["native"])} for uid, row in rows.items()}, check_score_wires)
    flagged, matching, claim_counts = [], set(), Counter()
    for digest, entry in unique.items():
        expected = entry["target"]
        claims = explicit_target_claims(entry["reason"], len(expected))
        if claims:
            claim_counts["has_explicit_recognized_claim"] += 1
        for claim in claims:
            bad = [{"position": i, "wire_target": expected[i - 1], "stated_target": value}
                   for i, value in claim["labels"].items() if expected[i - 1] != value]
            if bad:
                flagged.append({"locations": entry["locations"], "request_sha256": digest,
                                "target": expected, "excerpt": claim["quote"], "positions": bad})
                matching.add(digest)

    scored_methods = (method.ATOMIC, method.BUNDLED, method.ORDINARY)
    flagged_uids = {location["uid"] for entry in flagged for location in entry["locations"]}
    original = [row for row in rows.values() if all(row["native"][arm]["fields"].get("match") for arm in scored_methods)]
    retained = [row for row in original if row["uid"] not in flagged_uids]

    def sensitivity(sample):
        return {"paired_histories": len(sample), "source_groups": len({row["group"] for row in sample}),
                "positions": sum(row["positions"] for row in sample),
                "match": {arm: sum(row["native"][arm]["fields"]["match"]["matched"] for row in sample)
                          for arm in scored_methods}}

    return {"judge_arms": scored_methods, "logical_statuses": inspected, "distinct_reasons_checked": len(unique),
            "explicit_recognized_claims_by_request": claim_counts, "flagged_requests": len(matching),
            "flagged_histories": len(flagged_uids), "flagged_explicit_target_claims": flagged,
            "native_original_common": sensitivity(original),
            "sensitivity_excluding_flagged_histories": sensitivity(retained),
            "flagged_match_stress_test": {arm: flagged_match_bounds(original, method.ATOMIC, arm, matching)
                                          for arm in (method.BUNDLED, method.ORDINARY)},
            "new_requests": 0, "changed_native_scores": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("panel", choices=("smoke", "pilot"))
    args = parser.parse_args()
    out = run.BASE_OUT / args.panel
    if run.read(out / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Run has not settled")
    print(json.dumps(audit(run.read(out / "SETTLED.json")), ensure_ascii=False, indent=2))
