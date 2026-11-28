"""Check whether each executed removal could change the archived specialist's Actor input."""
from collections import Counter, defaultdict
import json

from trial import BASE, PRIVATE, archive, prepare, sha


def audit():
    pin, cards, _, _ = prepare()
    if archive.read(PRIVATE / "FROZEN.json") != pin:
        raise ValueError("Frozen roster drift")
    outcomes = archive.read(PRIVATE / "RESULTS.json")["audits"]
    endpoints = {r["uid"]: r for r in archive.read(BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    bank = {}
    for row in archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json"):
        if row["uid"] in cards and row["method"] == archive.engine.RP and row["actor_status"] == "OK":
            bank[row["uid"]] = row
    for benchmark, method in (("PersistBench", "PB_RUBRIC"), ("BenchPreS", archive.engine.GATE)):
        cases, _, _ = archive.transfer.context(benchmark)
        exposed = {uid: case for uid, case in cases.items() if uid in cards}
        for row in archive.transfer.archived_answers(benchmark, exposed):
            if row["method"] == method and row["actor_status"] == "OK":
                bank[row["uid"]] = row

    counts = defaultdict(Counter)
    overlaps = []
    for uid, card in cards.items():
        removed = set(outcomes[uid].get("removed", []))
        if not removed:
            continue
        benchmark = card["benchmark"]
        row = bank[uid]
        wire = row["actor_request"]
        if sha(wire) != row["actor_request_sha256"]:
            raise ValueError("Archived specialist request mismatch")
        answer = row["answer"]
        if benchmark == "RPEval":
            packet = json.loads(wire["messages"][1]["content"])
            if endpoints[uid]["old_route"] == "REUSE_RP":
                visible = {s["memory_id"] for s in packet["source_evidence"]}
            else:
                root = {"archived_actor_request": wire, "archived_actor_sha256": sha(wire),
                        "public_task": {k: packet[k] for k in ("query", "facts", "current_context")},
                        "original_sources": packet["source_evidence"],
                        "archived_policy": packet["preference_use_policy"]}
                task_wire = archive.v41.task_only_request(root)
                if json.loads(task_wire["messages"][1]["content"])["source_evidence"]:
                    raise ValueError("Empty-history endpoint includes original sources")
                answer = endpoints[uid]["no_history_state"]["answer"]
                visible = set()
        else:
            submitted = "\n".join(message["content"] for message in wire["messages"]
                                  if message["role"] in {"system", "user"}
                                  and isinstance(message["content"], str))
            visible = {s["memory_id"] for s in card["packet"]["source_evidence"] if s["text"] in submitted}
        if sha(answer) != card["baseline_answer_sha256"]:
            raise ValueError("Archived answer does not match the frozen reference")
        overlap = removed & visible
        counts[benchmark]["changed_matched_actor"] += 1
        counts[benchmark]["overlap_roots"] += bool(overlap)
        counts[benchmark]["overlap_sources"] += len(overlap)
        if overlap:
            overlaps.append({"uid": uid, "shared_removals": len(overlap)})
    return {"counts": counts, "overlaps": overlaps}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
