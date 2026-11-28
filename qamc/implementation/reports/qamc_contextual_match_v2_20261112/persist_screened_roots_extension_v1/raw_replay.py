"""Rebuild each logical result from exact frozen wires and physical receipts offline."""
from collections import Counter, defaultdict
from itertools import product
import json

from first_draw import (POLICIES, PRIVATE, ROOT, RUN, actor_request, extend, grade,
                        judge_wire, prepare, read, select, sha)
from readout import verify


def recover(stage, jobs, report):
    archive, _ = extend.archived(jobs, ROOT)
    local = {}
    for path in (RUN / stage / "visible").glob("*/record.json"):
        record = read(path)
        uid, arm = (record["unit"][k] for k in ("root_id", "method"))
        key = uid, arm
        if key in local or key in archive or key not in jobs:
            raise ValueError(f"Unexpected physical record in {stage}")
        expected = jobs[key]
        if read(path.with_name("request.json")) != expected or record["request_sha256"] != sha(expected):
            raise ValueError(f"Actual {stage} wire changed")
        if record["status"] in {"PENDING_DELIVERY_UNKNOWN", "STARTED"}:
            raise ValueError(f"Unsettled receipt in {stage}")
        answer = read(path.with_name("response.json"))["answer"] if record["status"] == "OK" else None
        local[key] = {"answer": answer, "status": record["status"]}
    if set(local) | set(archive) != set(jobs):
        raise ValueError(f"Incomplete lineage for {stage}")
    expected = report[stage]
    if (len(archive) != expected["exact_cache"]
            or dict(Counter(r["status"] for r in archive.values())) != expected["cached_status"]):
        raise ValueError(f"Archived {stage} inventory has changed")
    return {**archive, **local}


def observed_option(rating, track):
    if rating is None:
        return (0, 1)
    return (int(rating == 3 if track == "beneficial_memory_usage" else rating < 3),)


def paired_bound(score, track, alias):
    left, right = score
    if alias:
        if left != right:
            raise ValueError("Shared answer has inconsistent scores")
        return 0, 0
    deltas = [a - b for a, b in product(observed_option(left, track), observed_option(right, track))]
    return min(deltas), max(deltas)


def replay():
    checked = verify()
    pin, items, protocol, judge, envelopes = prepare()
    if read(RUN / "FROZEN_PREFLIGHT.json") != pin:
        raise ValueError("Invalid roster fingerprint")
    result = read(PRIVATE / "RESULTS.json")
    original = {row["uid"]: row for row in result["rows"]}
    cached = dict(zip(("FixedRouteSelection", "ExtensionActor", "ExtensionJudge"),
                      (result["cache"][k] for k in ("selection", "actor", "judge")), strict=True))
    extend.RUN = RUN
    selectors = recover("FixedRouteSelection", {(u, "SELECTED"): r["select"] for u, r in items.items()}, cached)
    wires, counts, endpoints = {}, {}, {}
    for uid, item in items.items():
        for arm in ("FULL", "EMPTY", "RUBRIC"):
            wires[uid, arm] = item[arm]
        reply = selectors[uid, "SELECTED"]
        if reply["status"] == "OK":
            try:
                selected = select(item["case"], item["public"], item["route_answer"], reply["answer"])
            except (KeyError, TypeError, ValueError):
                continue
            counts[uid] = len(selected)
            endpoints[uid] = "FULL" if selected else "EMPTY"
            wires[uid, "SELECTED"] = actor_request(item["case"], item["public"]["query"], selected, protocol,
                                                   protocol["prompts"]["gepa"])
    canonical, mapping = {}, {}
    for k, body in wires.items():
        mapping[k] = canonical.setdefault(sha(body), k)
    actors = recover("ExtensionActor", {k: wires[k] for k in canonical.values()}, cached)
    score_wire = judge_wire({u: r["case"] for u, r in items.items()}, items, judge, envelopes)
    judge_jobs = {k: score_wire(k[0], receipt["answer"]) for k, receipt in actors.items()
                  if receipt["status"] == "OK"}
    scores = recover("ExtensionJudge", judge_jobs, cached)
    same_input = defaultdict(Counter)
    bounds = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for uid, item in items.items():
        track = item["case"]["category"]
        row = {"uid": uid, "track": track, "subsets": counts.get(uid), "ratings": {}, "actor_status": {}}
        keys = {arm: mapping.get((uid, endpoints.get(uid) if arm == "GROUP" else arm)) for arm in POLICIES}
        for arm, key in keys.items():
            row["actor_status"][arm] = actors.get(key, {}).get("status", "UNISSUED")
            row["ratings"][arm] = grade(scores.get(key, {}).get("answer"), track)
        if original[uid] != row:
            raise ValueError("Raw replay disagrees with published per-root structure")
        for arm in POLICIES[1:]:
            equal = keys[arm] is not None and keys[arm] == keys["SELECTED"]
            same_input[track][arm] += int(equal)
            delta = paired_bound((row["ratings"]["SELECTED"], row["ratings"][arm]), track, equal)
            for i, d in enumerate(delta):
                bounds[track][arm][i] += d
    return {"replayed_logical_paths": len(items) * len(POLICIES), "same_actor_as_selected": same_input,
            "selected_pass_delta_by_allocation": bounds, **checked}


if __name__ == "__main__":
    print(json.dumps(replay(), sort_keys=True, indent=2))
