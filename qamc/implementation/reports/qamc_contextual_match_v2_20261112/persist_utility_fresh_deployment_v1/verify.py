"""Reconcile the settled summary with pre-registered roots and individual receipts."""
import json
from collections import Counter
from summary import RUN, report


def verify():
    result = report()
    saved = json.loads((RUN / "private/SETTLED.json").read_text())
    frozen = json.loads((RUN / "private/FROZEN.json").read_text())
    rows = saved["rows"]
    assert set(frozen["inputs"]) == {row["uid"] for row in rows}
    assert len(rows) == 54 and result["assigned"] == 18
    assert len({(row["uid"], row["arm"]) for row in rows}) == 54
    counts = Counter()
    statuses = Counter()
    tokens = retries = unknown_usage = over_cap = 0
    for stage in ("Route", "Select", "Actor", "GPT", "Qwen"):
        for path in (RUN / stage / "visible").glob("*/record.json"):
            record = json.loads(path.read_text())
            statuses[record["status"]] += 1
            counts[stage] += 1
            usage = record.get("usage") or {}
            tokens += usage.get("total_tokens") or 0
            unknown_usage += usage.get("total_tokens") is None
            retries += record["automatic_retries"]
            over_cap += bool(record.get("reported_completion_over_requested"))
    assert sum(counts.values()) == result["requests"]
    assert statuses == result["status"]
    assert tokens == result["tokens"] and unknown_usage == result["unknown_usage"]
    assert retries == 0
    for judge in ("GPT", "Qwen"):
        for arm in ("FULL", "RUBRIC", "SELECTED"):
            ratings = [row[judge] for row in rows if row["arm"] == arm]
            table = result["tables"][judge][arm]
            assert len(ratings) == 18
            assert table["pass"] == ratings.count(3)
            assert table["unknown"] == ratings.count(None)
            assert all(rating is None or rating in (1, 2, 3) for rating in ratings)
    print(json.dumps(dict(stage_requests=counts, automatic_retries=retries,
                          reported_completion_over_requested=over_cap), indent=2))


if __name__ == "__main__":
    verify()
