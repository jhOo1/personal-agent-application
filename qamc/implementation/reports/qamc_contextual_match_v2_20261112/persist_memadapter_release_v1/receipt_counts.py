"""Read-only counts per physical deployment stage, including wire/usage disagreement."""
from collections import Counter
import json
from pathlib import Path
import sqlite3

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name


def counts(path):
    receipts = {}
    for file in (path.parent/"visible").glob("*/record.json"):
        rec = json.loads(file.read_text())
        key = rec["request_sha256"]
        if key in receipts:
            raise ValueError("Duplicate physical receipt within draw/stage")
        receipts[key] = rec
    states, outcomes, combined, usage = Counter(), Counter(), Counter(), Counter()
    with sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True) as db:
        for key, status, cap in db.execute("""
            SELECT request_sha, status, json_extract(request_json,'$.max_tokens')
            FROM samples
        """):
            states[status] += 1
            rec = receipts.get(key, {})
            outcome = rec.get("status", "NO_VISIBLE_RECEIPT_YET")
            outcomes[outcome] += 1
            combined[status+" / "+outcome] += 1
            used = (rec.get("usage") or {}).get("completion_tokens")
            if used is not None:
                usage["known_completion_usage"] += 1
                usage["reported_above_requested_max"] += int(used > cap)
                usage["max_reported_completion"] = max(used,usage["max_reported_completion"])
    return dict(samples=states, transport=outcomes, paired_status=combined, usage=usage)



if __name__ == "__main__":
    print(json.dumps({p.parent.name:counts(p) for p in sorted(RUN.glob("D*/samples.sqlite"))},indent=2))
