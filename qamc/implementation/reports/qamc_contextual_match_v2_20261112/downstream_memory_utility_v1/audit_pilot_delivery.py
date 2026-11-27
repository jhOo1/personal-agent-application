"""Verify actual shared packets, intervention coverage, and final-answer provenance."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

from run_car import ARMS, RUN, preflight, probe


def inspect(results, cards, manifest):
    by_uid = {c["root"]["uid"]: c for c in cards}
    inputs = defaultdict(dict)
    for job in manifest["units"]:
        unit = job["unit"]
        uid, arm = unit["root_id"], unit["method"]
        wire = job["request"]
        if arm in inputs[uid] or arm not in ARMS or uid not in by_uid:
            raise ValueError("Duplicate or unexpected final-stage unit")
        inputs[uid][arm] = wire
    coverage = defaultdict(Counter)
    for uid, card in by_uid.items():
        outcome = coverage[card["benchmark"]]
        outcome["assigned"] += 1
        if inputs[uid].keys() != set(ARMS):
            if inputs[uid]:
                raise ValueError("The final stage did not supply all three matched arms")
            outcome["no_final_packet"] += 1
            continue
        wires = inputs[uid]
        shared = wires["WHOLE"]["messages"][1]
        for w in wires.values():
            if w["messages"][1] != shared or {k: v for k, v in w.items() if k != "messages"} != {
                    k: v for k, v in wires["WHOLE"].items() if k != "messages"}:
                raise ValueError("Final control input or execution settings drifted")
        packet = json.loads(shared["content"])
        root = card["root"]
        if (set(packet) != {"task", "source_evidence", "candidates", "opportunity", "fallback", "protected_literals"}
                or packet["task"] != root["public_task"] or packet["source_evidence"] != root["original_sources"]):
            raise ValueError("Task, sources, or private data projection changed")
        rendered = {key: "".join(blocks) for key, blocks in packet["candidates"].items()}
        if sha(rendered[packet["fallback"]]) != card["baseline_answer_sha256"]:
            raise ValueError("Strong fallback changed")
        proposal = packet["opportunity"]
        outcome["shared_controller_packet"] += 1
        if proposal is not None:
            outcome["proposed_action"] += 1
            outcome["proposal_cites_original_source"] += bool(proposal["evidence"])
        if "D" in rendered:
            outcome["donor_present"] += 1
            outcome["distinct_donor"] += rendered["D"] not in (rendered["T"], rendered["H"], rendered["F"])
        state = [r for r in results["rows"] if r["uid"] == uid and r["method"] == "COMMIT"]
        if len(state) != 1:
            raise ValueError("Expected one COMMIT outcome slot per task")
        row = state[0]
        if row.get("outcome") != "COMMITTED":
            continue
        outcome["nontrivial_commit"] += 1
        outcome["from_action_donor"] += row["donor"] == "D"
        if row["answer"] in rendered.values() or row["copied_blocks"] < 1:
            raise ValueError("Committed output failed the nontrivial copy requirement")
    return coverage


if __name__ == "__main__":
    plan, cards = preflight()
    if probe.read(RUN / "FROZEN.json") != plan:
        raise ValueError("Frozen delivery audit does not match the experiment")
    results = probe.read(RUN / "RESULTS.json")
    path = RUN / "Final_MANIFEST.json"
    print(json.dumps(inspect(results, cards, probe.read(path) if path.exists() else {"units": []}),
                     indent=2, sort_keys=True))
