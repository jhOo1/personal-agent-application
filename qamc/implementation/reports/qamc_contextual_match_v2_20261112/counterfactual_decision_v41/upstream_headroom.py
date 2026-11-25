"""Bound native errors that a correction of the archived RP policy could target."""
from collections import Counter, defaultdict
import json

from audit_completed import audited_rows
from intervention import archived_packet
from label_bounds import EVENTS, PROTECTED_LABEL, cell_bounds
from run_v41 import OUT, RP, read


TARGETS = dict(zip(EVENTS, ("BC", "A", "C", "A", "B"), strict=True))


def overlap(event_range, eligible, total):
    """Sharp overlap bounds for an unidentified set of errors of one label."""
    lo, hi = event_range
    if not 0 <= lo <= hi <= total or not 0 <= eligible <= total:
        raise ValueError("Impossible error or policy subset size")
    return max(0, lo - (total - eligible)), min(hi, eligible)


def counts(labels, policy, fields):
    match = fields["match"]
    if len(labels) != len(policy) or len(labels) != match["positions"] or set(policy) - set("ABC"):
        raise ValueError("Policy and native positions are not aligned")
    n = len(labels)
    errors = n - match["matched"]
    mismatches = sum(a != b for a, b in zip(labels, policy, strict=True))
    a, b = overlap((errors, errors), mismatches, n)
    output = Counter(roots=1, positions=n, native_errors=errors, policy_mismatches=mismatches,
                     native_errors_on_mismatch_min=a, native_errors_on_mismatch_max=b,
                     native_errors_on_policy_agreement_min=errors - b,
                     native_errors_on_policy_agreement_max=errors - a)
    bounds = cell_bounds(labels, fields)
    for lens, events in bounds.items():
        if events is None:
            output[lens + ".incompatible_roots"] += 1
            continue
        output[lens + ".roots"] += 1
        for event, label, limits in zip(EVENTS, PROTECTED_LABEL, events, strict=True):
            total = labels.count(label)
            eligible = sum(a == label and b in TARGETS[event] for a, b in zip(labels, policy, strict=True))
            onlo, onhi = overlap(limits, eligible, total)
            offlo, offhi = overlap(limits, total - eligible, total)
            prefix = f"{lens}.{event}."
            output.update({prefix + key: val for key, val in {
                "positions": total, "at_same_upstream_error": eligible,
                "native_error_min": limits[0], "native_error_max": limits[1],
                "native_error_on_policy_subset_min": onlo, "native_error_on_policy_subset_max": onhi,
                "native_error_outside_policy_subset_min": offlo, "native_error_outside_policy_subset_max": offhi,
            }.items()})
    return output


def analyze():
    plan = read(OUT / "FROZEN.json")
    terminal = read(OUT / "TERMINAL.json")
    if not terminal["primary_panel"]["complete"]:
        raise ValueError("Require terminal V41 evidence")
    roots = {root["uid"]: root for root in plan["roots"]}
    report = defaultdict(Counter)
    groups = defaultdict(set)
    observed = set()
    for batch, _ in audited_rows(plan):
        for row in batch:
            uid, labels = row["uid"], row["labels"]
            root = roots[uid]
            fields = row["native"][RP]["fields"]
            observed.add(uid)
            if "match" not in fields:
                continue
            _, packet = archived_packet(root)
            if [item["memory_id"] for item in packet["preference_use_policy"]] != [
                item["memory_id"] for item in packet["source_evidence"]
            ]:
                raise ValueError("Wire policy and native source positions differ")
            policy = "".join(item["policy"] for item in packet["preference_use_policy"])
            result = counts(labels, policy, fields)
            history = "all_A" if set(labels) == {"A"} else "contains_BC"
            exposure = "less_exposed" if row["in_sensitivity"] else "additional_groups"
            for key in ("all", history, exposure, f"{exposure}/{history}"):
                report[key].update(result)
                groups[key].add(row["group"])
    if observed != roots.keys():
        raise ValueError("Incomplete terminal panel")
    return {
        "planned_roots": len(observed), "comparator": RP, "new_model_requests": 0, "scores_modified": 0,
        "partitions": {key: {**vals, "source_groups": len(groups[key])} for key, vals in report.items()},
        "interpretation": ("These are feasibility intervals under the published scoring contract. "
                           "The same-index overlap is not a causal attribution. Policy correction could "
                           "also affect other positions. The overall and event-specific intervals "
                           "apply separately. Do not sum different event extrema."),
    }


def self_check():
    assert overlap((6, 6), 4, 7) == (3, 4)
    assert overlap((1, 5), 2, 5) == (0, 2)
    x = counts("AAAA", "AABB", {"match": {"matched": 1, "positions": 4}})
    assert (x["native_errors_on_mismatch_min"], x["native_errors_on_mismatch_max"]) == (1, 2)
    assert x["match_only.A_misuse.native_error_outside_policy_subset_min"] == 1


if __name__ == "__main__":
    self_check()
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
