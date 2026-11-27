"""Compare repeated induction receipts on identical requests without opening answers."""
from collections import Counter
import json

from costs import RUN


def receipts(draw):
    statuses = {}
    for path in (RUN / f"D{draw}MA1" / "visible").glob("*/record.json"):
        row = json.loads(path.read_text())
        digest = row["request_sha256"]
        assert digest not in statuses
        assert row["requested_max_tokens"] == 8192
        assert row["automatic_retries"] == 0
        statuses[digest] = row["status"]
    return statuses


def summarize():
    draws = [receipts(draw) for draw in (1, 2, 3)]
    repeated = set(draws[1])
    assert len(draws[0]) == 29 and len(repeated) == 9
    assert repeated == set(draws[2]) and repeated <= set(draws[0])
    patterns = Counter(tuple(draw[digest] for draw in draws) for digest in repeated)
    return {
        "identical_requests_repeated_three_times": len(repeated),
        "draw_order_patterns": {" / ".join(p): n for p, n in sorted(patterns.items())},
        "known_success_and_length_on_same_request": sum(
            n for p, n in patterns.items() if "OK" in p and "KNOWN_LENGTH_FAILURE" in p
        ),
        "length_in_all_three": patterns[("KNOWN_LENGTH_FAILURE",) * 3],
        "ok_in_all_three": patterns[("OK",) * 3],
    }


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
