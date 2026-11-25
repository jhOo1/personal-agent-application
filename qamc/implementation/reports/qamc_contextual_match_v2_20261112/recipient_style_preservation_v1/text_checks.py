"""Check realized draft mutations independently of model judgment."""
from collections import Counter
import json
from pathlib import Path
import re
from runpy import run_path

HERE = Path(__file__).resolve().parent
m = run_path(str(HERE / "run.py"))
NUMERIC = re.compile(r"(?<!\w)\d(?:\d|[,.\-/](?=\d))*(?:[%°]|[a-z]{1,2}\b)?", re.I)


def evaluate():
    _, roots, *_ = m["prepare"]()
    m["probe"].OUT = HERE
    m["probe"].RUN = m["RUN"]
    responses = m["probe"].stage_receipts(m["ACTOR"])
    cases = []
    for (uid, arm), (record, payload) in responses.items():
        root = roots[uid]
        before = root["draft"]
        if record["status"] != "OK":
            cases.append({"uid": uid, "method": arm, "status": record["status"]})
            continue
        try:
            after, edits, issues = m["materialize"](payload, arm, root)
        except (ValueError, TypeError) as err:
            after, edits, issues = before, [], [str(err)]
        nums_before, nums_after = (Counter(NUMERIC.findall(x)) for x in (before, after))
        old, new = ([line.strip() for line in s.splitlines() if line.strip()] for s in (before, after))
        case = {"uid": uid, "method": arm, "status": "OK", "changed": before != after,
                "words_before": len(before.split()), "words_after": len(after.split()),
                "name_before": bool(root["sender"] and root["sender"] in before),
                "name_after": bool(root["sender"] and root["sender"] in after),
                "first_and_last_lines_equal": old[:1] == new[:1] and old[-2:] == new[-2:],
                "protected_equal": m["protected"](before, root["sender"]) == m["protected"](after, root["sender"]),
                "numeric_strings_added": dict(nums_after - nums_before),
                "numeric_strings_removed": dict(nums_before - nums_after),
                "applied_edits": len(edits), "issues": issues}
        if arm == "STYLE_SLOTS" and (not case["first_and_last_lines_equal"] or not case["protected_equal"]):
            raise ValueError("Bounded edit violated a declared protection")
        cases.append(case)
    return cases


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, indent=2, ensure_ascii=False))
