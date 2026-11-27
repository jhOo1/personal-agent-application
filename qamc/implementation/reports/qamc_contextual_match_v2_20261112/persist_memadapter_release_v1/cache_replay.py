"""Chronological stage-one cache replay. Match stage-two requests in the same draw."""
import json
from collections import Counter
from competition import BU, RUN, author_module, author_wire, inputs, read, sha


def records(draw, stage):
    index = {}
    for path in (RUN / f"D{draw}{stage}" / "visible").glob("*/record.json"):
        row = read(path)
        key = sha(read(path.with_name("request.json")))
        assert key == row["request_sha256"] and key not in index
        index[key] = (row, path)
    return index


def replay():
    mod = author_module()
    _, cases, tasks = inputs()
    cache = {}
    counts = Counter()
    skipped_usage = Counter()
    for draw in range(1, 4):
        first, second = records(draw, "MA1"), records(draw, "MA2")
        for uid, task in tasks.items():
            if draw > 1 and cases[uid]["category"] == BU:
                continue
            key = sha(author_wire(mod, task, 1))
            row, path = first[key]
            counts["deployments"] += 1
            if key in cache:
                counts["prior_valid_cache"] += 1
                skipped_usage["known_tokens"] += (row["usage"] or {}).get("total_tokens", 0)
                skipped_usage["unknown_usage"] += row["usage"] is None
                second_key = sha(author_wire(mod, task, 2, cache[key]))
                counts["identical_second_request_this_draw"] += second_key in second
                counts["new_second_request_needed"] += second_key not in second
                counts["previously_failed_inductions_bypassed"] += row["status"] != "OK"
            elif row["status"] == "OK":
                answer = read(path.with_name("response.json"))["answer"]
                assert sha(author_wire(mod, task, 2, answer)) in second
                cache[key] = answer
    assert counts["deployments"] == 47
    return dict(counts=counts, skipped_stage_one_receipts=skipped_usage)


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2))
