"""Read-only counts per physical deployment stage, including wire/usage disagreement."""
from collections import Counter
import json
from pathlib import Path
import sqlite3

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[2] / "runs" / HERE.parent.name / HERE.name


def counts(path):
    result = Counter()
    with sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True) as db:
        for status, cap, used in db.execute("""
            SELECT status, json_extract(request_json,'$.max_tokens'),
                   json_extract(response_json,'$.usage.completion_tokens')
            FROM samples
        """):
            result[status] += 1
            if used is not None:
                result["known_completion_usage"] += 1
                result["reported_above_requested_max"] += int(used > cap)
                result["max_reported_completion"] = max(used,result["max_reported_completion"])
    return dict(result)


if __name__ == "__main__":
    print(json.dumps({p.parent.name:counts(p) for p in sorted(RUN.glob("D*/samples.sqlite"))},indent=2))
