"""Verify actual request contrast and exact response agreement without model calls."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import sha


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(run):
    manifest = read(run / "private" / "BoundaryActor_MANIFEST.json")
    requests = {}
    for item in manifest["units"]:
        unit = item["unit"]
        group = requests.setdefault(unit["root_id"], {})
        require(unit["method"] not in group, "Duplicate actor manifest unit")
        group[unit["method"]] = item["request"]

    responses, states = {}, Counter()
    for path in sorted((run / "BoundaryActor" / "visible").glob("*/record.json")):
        saved = read(path)
        uid, arm = (saved["unit"][key] for key in ("root_id", "method"))
        require(saved["request_sha256"] == sha(requests[uid][arm]), "Receipt wire does not match")
        states[(arm, saved["status"])] += 1
        if saved["status"] == "OK":
            responses[uid, arm] = read(path.with_name("response.json"))["answer"]

    agreement = Counter()
    for uid, group in requests.items():
        first, last, split = (group[arm] for arm in ("TASK_FIRST", "TASK_LAST", "TASK_SEPARATE"))
        first_turns, last_turns, split_turns = (wire["messages"] for wire in (first, last, split))
        require(first_turns[0] == last_turns[0] == split_turns[0], "System message changed by arm")
        request_settings = [{k: v for k, v in wire.items() if k != "messages"} for wire in (first, last, split)]
        require(request_settings[0] == request_settings[1] == request_settings[2], "Actor settings changed by arm")
        require([m["role"] for m in split_turns] == ["system", "user", "user"], "Wrong split roles")
        pair = [msg["content"] for msg in split_turns[1:]]
        require(last_turns[1:] == [{"role": "user", "content": "\n".join(pair)}], "Last content changed")
        require(first_turns[1:] == [{"role": "user", "content": "\n".join(reversed(pair))}], "First content changed")
        for compared in ("TASK_FIRST", "TASK_SEPARATE"):
            other, normal = (responses.get((uid, arm)) for arm in (compared, "TASK_LAST"))
            if other is not None and normal is not None:
                agreement[f"{compared}_paired"] += 1
                agreement[f"{compared}_exact_response_agreement"] += other == normal

    return {"matched_wires": len(requests),
            "states": {"/".join(key): value for key, value in states.items()},
            "response_agreement": dict(agreement)}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.run), indent=2))


if __name__ == "__main__":
    main()
