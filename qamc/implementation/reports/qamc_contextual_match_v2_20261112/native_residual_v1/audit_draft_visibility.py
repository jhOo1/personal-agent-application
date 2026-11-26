"""Verify the paired intervention and aggregate only complete PersistBench pairs."""
import json
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent / "persist_draft_visibility_v1"
ARMS = ("REVISE", "RESOLVE")


def read(name):
    return json.loads((OUT / name).read_text())


def audit_wires():
    requests = defaultdict(dict)
    for item in read("FinalActor_MANIFEST.json")["units"]:
        unit, request = item["unit"], item["request"]
        requests[unit["root_id"]][unit["method"]] = request
    for uid, pair in requests.items():
        for arm in ARMS:
            request = pair[arm]
            if len(request["messages"]) != 2:
                raise ValueError(f"Unexpected message shape: {uid}")
        left, right = (pair[arm] for arm in ARMS)
        old, new = (json.loads(request["messages"][1]["content"]) for request in (left, right))
        draft = old.pop("draft")
        if old != new or left["messages"][0] != right["messages"][0] or not draft:
            raise ValueError(f"Paired actor input drift: {uid}")
        envelope = lambda request: {key: val for key, val in request.items() if key != "messages"}
        if envelope(left) != envelope(right):
            raise ValueError(f"Paired settings drift: {uid}")
        if draft in (new["proposal"]["action"] or ""):
            raise ValueError(f"Shared proposal contains the complete draft: {uid}")
    return len(requests)


def summarize():
    data = read("RESULTS.json")
    cases = defaultdict(dict)
    for row in data["rows"]:
        cases[row["uid"]][row["method"]] = row
    counts = defaultdict(Counter)
    for pair in cases.values():
        left, right = (pair[arm] for arm in ARMS)
        category = left["category"]
        row = counts[category]
        row["planned"] += 1
        if left["score"] is None or right["score"] is None:
            row["missing"] += 1
            continue
        flag = "failure_strict_utility" if category == "beneficial_memory_usage" else "failure_release"
        base, revise, resolve = (not score[flag] for score in
                                 (left["base_score"], left["score"], right["score"]))
        row.update({"n": 1, "base_pass": base, "revise_pass": revise, "resolve_pass": resolve,
                    "resolve_win": resolve and not revise, "resolve_loss": revise and not resolve})
    ledger = data["ledger"]
    return {"verified_request_pairs": audit_wires(), "metrics": counts,
            "abstentions": sum(x["action"] is None for x in data["proposals"].values()),
            "statuses": Counter(row["status"] for row in ledger),
            "reported_tokens": sum((row["usage"] or {}).get("total_tokens", 0) for row in ledger),
            "unknown_usage": sum(row["usage"] is None for row in ledger)}


if __name__ == "__main__":
    if (OUT / "RESULTS.json").is_file():
        print(json.dumps(summarize(), indent=2))
    else:
        print(f"Verified {audit_wires()} request pairs. Grading not settled.")
