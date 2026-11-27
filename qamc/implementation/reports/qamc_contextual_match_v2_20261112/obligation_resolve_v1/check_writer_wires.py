"""Audit the persisted writer request bodies without exposing text or running models."""
import argparse
from collections import Counter
import json
from pathlib import Path


def check(wires):
    groups = {}
    for key, wire in wires.items():
        uid, arm = key.rsplit("/", 1)
        groups.setdefault(uid, {})[arm] = wire
    counts = Counter()
    for arms in groups.values():
        if set(arms) != {"ISOLATED", "LOCAL_EDIT", "FREE"}:
            raise ValueError("Missing writer assignment")
        visible, hidden = (arms[a] for a in ("LOCAL_EDIT", "ISOLATED"))
        for obj in (visible, hidden):
            if [msg["role"] for msg in obj["messages"]] != ["system", "user"]:
                raise ValueError("Unexpected message sequence")
        def config(wire):
            return {k: v for k, v in wire.items() if k != "messages"}
        assert config(visible) == config(hidden) == config(arms["FREE"])
        assert visible["messages"][0] == hidden["messages"][0]
        assert visible["messages"][1] == arms["FREE"]["messages"][1]
        left, right = [json.loads(obj["messages"][1]["content"]) for obj in (visible, hidden)]
        units = left.pop("draft_units")
        masked = right.pop("draft_units")
        assert left == right
        targets = set(left["writable"])
        ids = [u["id"] for u in units]
        assert len(ids) == len(set(ids)) and targets and targets <= set(ids)
        expected = [{k: v for k, v in u.items() if k != "text"} if u["id"] in targets else u for u in units]
        assert expected == masked
        counts["targets"] += len(targets)
        counts["multiple_targets"] += int(len(targets) > 1)
    return {"writer_triplets": len(groups), **counts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_wires", type=Path)
    print(json.dumps(check(json.loads(parser.parse_args().private_wires.read_text())), indent=2))
