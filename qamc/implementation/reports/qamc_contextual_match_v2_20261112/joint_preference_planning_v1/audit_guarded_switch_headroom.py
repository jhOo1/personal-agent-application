"""Measure best-case protected selection between unchanged RP and new-admission answers."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_active_source_ids as trial


RP, NEW = trial.outcome.RP, trial.NEW
PROTECT = ("OPB", "UPB", "FM")


def audit():
    path = trial.OUT / "SETTLED.json"
    saved = trial.read(path)
    if trial.read(trial.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The source admission comparison has not settled")
    rows = saved["rows"]
    named = [row["group"] for row in rows if "e097bc15" in row["uid"]]
    if len(named) != 1:
        raise ValueError("Expected one assigned birthday anchor")
    birthday = named[0]
    group_counts, strata = defaultdict(Counter), defaultdict(Counter)
    cases, excluded = [], []
    for row in rows:
        native = row["native"]
        old, new = (native[arm]["fields"] for arm in (RP, NEW))
        if ("match" not in native[trial.OLD]["fields"]
                or not all("match" in entry and all(type(entry.get(f)) in (int, float) for f in PROTECT)
                           for entry in (old, new))):
            excluded.append(row["uid"])
            continue
        if any(entry["match"]["positions"] != row["positions"] for entry in (old, new)):
            raise ValueError("Native position count mismatch")
        delta = new["match"]["matched"] - old["match"]["matched"]
        harms = [field for field in PROTECT if new[field] > old[field]]
        gain = max(0, delta)
        protected = gain if not harms else 0
        label = "all_A" if set(row["labels"]) == {"A"} else "has_C" if "C" in row["labels"] else "B_only"
        counts = {"cases": 1, "positions": row["positions"], "RP": old["match"]["matched"],
                  "NEW": new["match"]["matched"], "potential_gain": gain, "protected_gain": protected,
                  "cases_with_protected_gain": int(protected > 0)}
        group_counts[row["group"]].update(counts)
        for section in (label, "all", "birthday" if row["group"] == birthday else "exclude_birthday"):
            strata[section].update(counts)
        cases.append({"uid": row["uid"], "group": row["group"], "numeric_gain": delta,
                      "harms": harms, "protected_gain": protected})
    positive_groups = [group for group, values in group_counts.items()
                       if group != birthday and values["protected_gain"] > 0]
    # Freeze practical headroom before computing results. Allow enough room for a
    # selector to miss some beneficial switches while still improving materially.
    all_rows, leave_out = strata["all"], strata["exclude_birthday"]
    checks = {"coverage": all_rows["cases"] == 50,
              "protected_overall_at_least_5pp": all_rows["protected_gain"] >= .05 * all_rows["positions"],
              "protected_nobirthday_at_least_3pp": leave_out["protected_gain"] >= .03 * leave_out["positions"],
              "multiple_positive_nonbirthday_groups": len(positive_groups) >= 2}
    fallback = draft_fallback(saved["rows"], {case["uid"] for case in cases}, birthday)
    return {"source_sha256": sha(path.read_bytes()), "physical_requests": 0, "birthday_group": birthday,
            "strata": strata, "groups": group_counts, "cases": cases, "excluded": excluded,
            "screen": checks, "dispatch_worthwhile": all(checks.values()), "posthoc_draft_fallback": fallback}


def draft_fallback(rows, eligible, birthday):
    """Sensitivity to retaining the original task-only draft instead of rewriting it."""
    _, _, _, history, (_, official, cases), _ = trial.outcome.prepare()
    cache = trial.prepare()[-1][trial.JUDGE]
    totals, groups = defaultdict(Counter), Counter()
    for row in rows:
        uid = row["uid"]
        if uid not in eligible:
            continue
        new = row["native"][NEW]["fields"]
        if not row["active_memory_ids"][NEW]:
            wire = trial.scorer.grade_request(official, cases[uid], history[uid]["draft"])
            receipt, raw = cache[sha(wire)]
            new = trial.scorer.parse_grade(receipt, raw, row["positions"])["fields"]
        rp = row["native"][RP]["fields"]
        gain = max(0, new["match"]["matched"] - rp["match"]["matched"])
        if any(new[metric] > rp[metric] for metric in PROTECT):
            gain = 0
        label = "all_A" if set(row["labels"]) == {"A"} else "has_C" if "C" in row["labels"] else "B_only"
        for section in ("all", label, "birthday" if row["group"] == birthday else "exclude_birthday"):
            totals[section].update(positions=row["positions"], protected_gain=gain)
        groups[row["group"]] += gain
    return {"strata": totals, "protected_gains_by_group": groups}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
