"""Validate compiler properties on exposed RPEval, BenchPreS and PersistBench inputs."""
from collections import Counter
import json

from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request

from contract import METHOD_PROMPTS, actor_request, compile_scope, selection_request, task_only_request
from run_v41 import OUT, RP, read
from transfer_replay import development


def public_roots():
    for root in read(OUT / "FROZEN.json")["roots"]:
        yield "RPEval", root
    cross = read(OUT.parent / "counterfactual_decision_v41" / "TRANSFER_REPLAY.json")
    ready = set(cross["verified_RP_sources_and_wires"])
    for row in read(development.OUT / "RESULT_ROWS.json"):
        if row["uid"] not in ready or row["method"] != RP:
            continue
        wire, view = row["actor_request"], row["view"]
        if sha(wire) != cross["verified_RP_sources_and_wires"][row["uid"]]["actor_sha256"]:
            raise ValueError("Cross-benchmark Actor receipt drift")
        root = {
            "uid": row["uid"], "public_task": {key: view[key] for key in ("query", "current_context", "facts")},
            "original_sources": view["source_evidence"], "archived_policy": view["preference_use_policy"],
            "archived_actor_sha256": sha(wire), "archived_actor_request": wire,
        }
        yield "BenchPreS" if row["uid"].startswith("benchpres/") else "PersistBench", root


def smoke():
    counts = Counter()
    for benchmark, root in public_roots():
        query = root["public_task"]["query"]
        anchors = [{"id": "D1", "anchor": query[:40], "beneficiary": "fixture only"}]
        original = root["original_sources"]
        # Mechanical fixtures. They are never sent to a model or used as semantic results.
        uses = [{"memory_id": item["memory_id"], "decision_id": "D1",
                 "level": "C" if i % 4 == 2 else "B", "source_quote": item["text"][:35]}
                for i, item in enumerate(original) if i % 2 == 0]
        response = {"decisions": anchors, "uses": uses}
        compiled = compile_scope(root, json.dumps(response, ensure_ascii=False))
        full, masked = (actor_request(root, compiled, masked=mode) for mode in (False, True))
        assert full["messages"][0] == masked["messages"][0]
        left, right = (json.loads(wire["messages"][1]["content"]) for wire in (full, masked))
        assert all(left.get(key) == right.get(key) for key in ("query", "current_context", "facts",
                                                             "memory_decision_scopes"))
        kept = {row["memory_id"] for row in compiled}
        assert left["source_evidence"] == original
        assert right["source_evidence"] == [src for src in original if src["memory_id"] in kept]
        assert right["preference_use_policy"] == [p for p in left["preference_use_policy"]
                                                   if p["memory_id"] in kept and p["policy"] != "A"]
        assert actor_request(root, [], masked=True) == task_only_request(root)
        requests = [selection_request(root, method) for method in METHOD_PROMPTS]
        assert requests[0]["messages"][1] == requests[1]["messages"][1]
        assert requests[0]["messages"][0] != requests[1]["messages"][0]
        assert "preference_use_policy" not in json.loads(requests[0]["messages"][1]["content"])
        for wire in (full, masked, *requests):
            validate_public_request(wire)
        if uses:
            response["uses"] = [{**uses[0], "source_quote": "invalid literal\x00"}]
            try:
                compile_scope(root, json.dumps(response, ensure_ascii=False))
            except ValueError:
                counts[benchmark + "_reject_invalid_quote"] += 1
            else:
                raise ValueError("Compiler permitted an unsupported quote")
        counts[benchmark] += 1
    assert {name: counts[name] for name in ("RPEval", "BenchPreS", "PersistBench")} == {
        "RPEval": 233, "BenchPreS": 48, "PersistBench": 58
    }
    return {"tested": counts, "new_model_calls": 0, "semantic_scores": 0,
            "sources_and_public_inputs": "matched existing exposed RP requests"}


if __name__ == "__main__":
    print(json.dumps(smoke(), ensure_ascii=False, indent=2))
