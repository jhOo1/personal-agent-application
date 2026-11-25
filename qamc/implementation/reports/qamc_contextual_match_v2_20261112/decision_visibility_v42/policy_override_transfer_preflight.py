"""Replay the same V43 wire contract on the two exposed transfer panels, offline."""
from collections import Counter
import json

from qamc.common import sha

from contract import compile_scope, selection_request
from run_policy_override_v43 import candidate, policy_only_request
from transfer_execution import bench_context, bench_pair, development_roots, persist_context, persist_pair, RP


def verify_packet(root):
    reference = root["archived_actor_request"]
    if policy_only_request(root, {}) != reference:
        raise ValueError("No-op changed an archived transfer request")
    direct, scoped = (selection_request(root, method)["messages"][1] for method in ("DIRECT", "SCOPED"))
    expected = {**root["public_task"], "source_evidence": root["original_sources"]}
    if direct != scoped or json.loads(direct["content"]) != expected:
        raise ValueError("Transfer Selector received different evidence or a private field")
    policy = {x["memory_id"]: x["policy"] for x in root["archived_policy"]}
    soft = [x for x in root["original_sources"] if policy[x["memory_id"]] == "B"]
    if not soft:
        return False
    # Only exercise contract shape. This does not nominate or score a real edit.
    source = soft[0]
    decision = {"id": "D1", "anchor": expected["query"][:30], "beneficiary": "offline fixture"}
    firm = {"memory_id": source["memory_id"], "decision_id": "D1", "level": "C",
            "source_quote": source["text"][:30]}
    for level, uses in (("A", []), ("C", [firm])):
        scope = compile_scope(root, json.dumps({"decisions": [decision], "uses": uses}))
        edits, outcome = candidate(root, {name: {"scope": scope} for name in ("DIRECT", "SCOPED")})
        if outcome != "CHANGED" or edits.get(source["memory_id"]) != level or any(
            policy[mid] != "B" for mid in edits
        ):
            raise ValueError("Transfer changed an ineligible RP policy")
        wire = policy_only_request(root, edits)
        actor = json.loads(wire["messages"][1]["content"])
        actual = {x["memory_id"]: x["policy"] for x in actor.pop("preference_use_policy")}
        if (actor != expected or actual != {**policy, **edits} or wire["messages"][0] != reference["messages"][0]
                or sha(wire) == root["archived_actor_sha256"]):
            raise ValueError("Transfer changed an Actor input beyond one policy field")
    return True


def run():
    results = {}
    for name, archive, scorer in (("BenchPreS", bench_context, bench_pair),
                                  ("PersistBench", persist_context, persist_pair)):
        roots = development_roots(name)
        eligible = {row["uid"] for row in roots if verify_packet(row)}
        cases, _, controls = archive()
        if cases.keys() != {row["uid"] for row in roots}:
            raise ValueError("Eligible plan and archived grading roots differ")
        scores = {(c["uid"], c["method"]): c["score"] for c in controls if c["score"] is not None}
        roles = sorted({c["method"] for c in controls} - {RP})
        partitions = {
            "has_RP_B": {uid: c for uid, c in cases.items() if uid in eligible},
            "cannot_change_no_RP_B": {uid: c for uid, c in cases.items() if uid not in eligible}
        }
        results[name] = {
            "roots": len(roots), "policy_positions": Counter(p["policy"] for r in roots for p in r["archived_policy"]),
            "eligibility": {tag: len(part) for tag, part in partitions.items()},
            "archived_pairs": {tag: {m: scorer(RP, m, part, scores) for m in roles}
                               for tag, part in partitions.items()},
        }
    return {"benchmarks": results, "fresh_model_calls": 0, "V43_semantic_scores": 0,
            "interpretation": "Structural edit reachability and old native scores, not predicted intervention coverage."}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
