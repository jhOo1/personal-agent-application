"""Evaluate bounded PersistBench policy edits with frozen source groups."""
import argparse
import json

from build_jobs import archive_inputs
from freeze_persist_policy_panel import OUT as PANEL, build
from persist_policy_block import locate, policy_wire
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha
from trial_reassembly import engine, grading, probe

OUT = PANEL.parent / "persist_policy_replace_recovery_v1"
RUN = engine.RUN.with_name(OUT.name)


def prepare():
    panel = probe.read(PANEL)
    if panel != build():
        raise ValueError("Panel drift")
    wires, cards = archive_inputs()
    search = {}
    for row in panel["rows"]:
        if row["split"] != "search":
            continue
        key = "PersistBench", row["uid"]
        search[row["uid"]] = wires[key]["actor_request"], cards[key]
    return panel, search


def run(check):
    panel, search = prepare()
    original = PANEL.parent / "persist_policy_search_v1"
    manifest = probe.read(original / "PolicyActor_MANIFEST.json")
    if any(row["unit"]["method"] == "replace" for row in manifest["units"]):
        raise ValueError("Replacement was already dispatched")
    receipts = engine.RUN.with_name(original.name) / "PolicyProposal" / "visible"
    matches = [path for path in receipts.glob("*/record.json")
               if probe.read(path)["unit"]["method"] == "replace"]
    receipt, = matches
    if probe.read(receipt)["status"] != "OK":
        raise ValueError("No successful replacement proposal to recover")
    data = json.loads(probe.read(receipt.with_name("response.json"))["answer"])
    if list(data) != ["text"] or not isinstance(data["text"], str):
        raise ValueError("Expected a single text field")
    mutation = data["text"]
    jobs = {(uid, "replace"): policy_wire(wire, sha(wire), mutation, "replace",
                                         byte_cap=panel["byte_cap"])
            for uid, (wire, _) in search.items()}
    for wire in jobs.values():
        validate_public_request(wire)
    caps = {"PolicyActor": 12, "PersistNative": 12}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([panel, sorted((list(key), sha(wire)) for key, wire in jobs.items()), caps, sha(__file_bytes())]),
    }
    if check:
        print(len(search), caps)
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, True, ledger, cache) if jobs else {}

        rows = []
        for (uid, mode), receipt in dispatch("PolicyActor", jobs).items():
            _, card = search[uid]
            answer = receipt["answer"] if receipt["status"] == "OK" else None
            rows.append({
                "uid": uid, "method": mode, "benchmark": "PersistBench", "group": card["group"],
                "stratum": card["stratum"], "sources": card["root"]["original_sources"],
                "answer": answer, "actor_status": receipt["status"], "base_score": card["base_score"],
                "score": card["base_score"] if answer == card["base_answer"] else None,
            })
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {
            "rows": rows, "ledger": ledger, "policies": {"replace": mutation}, "proposal_failures": {},
        })


def __file_bytes():
    return PANEL.with_name("run_persist_policy_replace_recovery.py").read_bytes()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    run(parser.parse_args().action == "check")
