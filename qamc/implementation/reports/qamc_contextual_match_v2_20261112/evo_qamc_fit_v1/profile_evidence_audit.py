"""Verify shared profile preparation and exact quote-only Actor contrasts."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path

from profile_evidence_restoration import ARMS, parse_profile
from qamc.common import sha


def read(path):
    return json.loads(path.read_text())


def inspect_stage(run, stage):
    path = run / "private" / f"{stage}_MANIFEST.json"
    if not path.is_file():
        return {}, {}
    wires = {}
    for item in read(path)["units"]:
        key = (item["unit"]["root_id"], item["unit"]["method"])
        if key in wires:
            raise ValueError("Duplicate registered unit")
        wires[key] = item["request"]
    receipts = {}
    for path in sorted((run / stage / "visible").glob("*/record.json")):
        row = read(path)
        key = (row["unit"]["root_id"], row["unit"]["method"])
        if row["request_sha256"] != sha(wires[key]) or read(path.with_name("request.json")) != wires[key]:
            raise ValueError("Stored request differs from registered input")
        receipts[key] = (row["status"], None)
        if row["status"] == "OK":
            receipts[key] = (row["status"], read(path.with_name("response.json"))["answer"])
    return wires, receipts


def user_data(wire):
    return json.loads(wire["messages"][1]["content"])


def expected_payloads(task, points):
    previous = [{"memory_id": p["source_id"], "profile": p["profile"]} for p in points]
    quoted = [{**p, "source_quote": q["quote"]} for p, q in zip(previous, points, strict=True)]
    return ({"task": task, "source_evidence": previous},
            {"task": task, "source_evidence": quoted})


def verify_pair(wires, expected):
    left, right = wires
    if user_data(left) != expected[0]:
        raise ValueError("Profile-only Actor changed its shared inputs")
    if user_data(right) != expected[1]:
        raise ValueError("Quoted Actor contains an unintended change")
    if left["messages"][0] != right["messages"][0]:
        raise ValueError("Actor system messages differ")
    if {k: v for k, v in left.items() if k != "messages"} != {
            k: v for k, v in right.items() if k != "messages"}:
        raise ValueError("Actor transport settings differ")


def audit(run):
    refine_wires, refinements = inspect_stage(run, "RefinedProfile")
    actor_wires, actors = inspect_stage(run, "ProfileActor")
    by_payload = {sha(user_data(wire)): wire for wire in actor_wires.values()}
    counts = defaultdict(Counter)
    for (uid, arm), wire in refine_wires.items():
        counter = counts[uid.split("/", 1)[0]]
        status, raw = refinements.get((uid, arm), ("UNISSUED", None))
        counter["refiner_" + status] += 1
        actors_for_task = [actor_wires.get((uid, method)) for method in ARMS]
        if status != "OK":
            if any(x is not None for x in actors_for_task):
                raise ValueError("Actor ran without a verified refinement")
            continue
        packet = user_data(wire)
        histories = packet["source_evidence"]
        counter["available_selected_sources"] += len(histories)
        try:
            points = parse_profile(raw, histories)
        except (KeyError, TypeError, ValueError):
            counter["invalid_profile"] += 1
            if any(x is not None for x in actors_for_task):
                raise ValueError("Actor ran after an invalid refinement")
            continue
        counter["valid_profile"] += 1
        counter["valid_points"] += len(points)
        counter["distinct_sources_represented"] += len({p["source_id"] for p in points})
        if not points:
            counter["empty_valid_profile"] += 1
            if len([w for w in actors_for_task if w is not None]) > 1:
                raise ValueError("Identical empty-profile requests must be deduplicated")
            continue
        if actor_wires:
            expected = expected_payloads(packet["task"], points)
            actors_for_task = [wire if wire is not None else by_payload.get(sha(payload))
                               for wire, payload in zip(actors_for_task, expected, strict=True)]
            if any(w is None for w in actors_for_task):
                raise ValueError("Quote-active point has no paired generation requests")
            verify_pair(actors_for_task, expected)
            counter["quote_only_verified_pairs"] += 1
    return {"domains": counts, "registered_actor_requests": len(actor_wires),
            "actor_status": Counter(status for status, _ in actors.values())}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.run), indent=2))


if __name__ == "__main__":
    main()
