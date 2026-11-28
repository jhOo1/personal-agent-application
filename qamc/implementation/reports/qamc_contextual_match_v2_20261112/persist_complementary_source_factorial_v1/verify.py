"""Verify what really changed between the twelve actor requests and full history."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from runpy import run_path

NOW = run_path(str(Path(__file__).with_name("trial.py")))
BLOCK = re.compile(r"<memories>\s*(.*?)\s*</memories>", re.DOTALL)


def normalize(wire):
    baseline = deepcopy(wire)
    message = baseline["messages"][0]
    blocks = BLOCK.findall(message["content"])
    assert len(blocks) == 1
    message["content"] = BLOCK.sub("<memories></memories>", message["content"])
    return baseline, blocks[0]


def main():
    pin, _, jobs, historical, cache, _ = NOW["build"]()
    read, sha = NOW["read"], NOW["sha"]
    assert pin == read(NOW["PRIVATE"] / "FREEZE.json")
    _, inputs, *_ = NOW["prepare"]()
    seen = {}
    counts = Counter()
    for path in NOW["RUN"].glob("Actor/visible/*/record.json"):
        record = read(path)
        wire = read(path.with_name("request.json"))
        assert sha(wire) == record["request_sha256"]
        seen[record["request_sha256"]] = wire
    for (uid, label), wire in jobs.items():
        digest = sha(wire)
        expected_full = inputs[uid]["FULL"]
        assert sha(expected_full) == historical[uid]["wire"]
        base, history = normalize(wire)
        reference, full_history = normalize(expected_full)
        assert base == reference
        pair = NOW["ROOTS"][uid.split("/")[-1][:8]]
        exclude = {i for i, admitted in zip(pair, NOW["CELLS"][label]) if not admitted}
        sources = inputs[uid]["public"]["memories"]
        positions = []
        for i, source in enumerate(sources):
            assert full_history.count(source) == 1
            assert history.count(source) == int(i not in exclude)
            if i not in exclude:
                positions.append(history.index(source))
        assert positions == sorted(positions)
        assert (digest in cache and digest not in seen) or seen[digest] == wire
        counts[label] += 1
    print(json.dumps({"verified_new_conditions": sum(counts.values()),
                      "verified_reused_both_conditions": len(historical),
                      "per_intervention": counts, "cached_actor_conditions": len(cache)}, indent=2))


if __name__ == "__main__":
    main()
