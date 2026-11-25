"""Freeze one recovery proposal per eligible, non-diagnostic scope-pilot task."""
import argparse
from pathlib import Path

from build_jobs import archive_inputs
from optional_recovery import compile_option, proposal_wire
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from run_scope_pilot import OUT as PARENT
from scope_planner import inputs
from trial_reassembly import engine, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "recovery_proposals_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "RecoveryPlan"
DIAGNOSTIC_UID = "rpeval/formal_multi_v1/explicit/030"


def main(action):
    saved = probe.read(PARENT / "RESULTS.json")
    wires, cards = archive_inputs()
    requests, contexts = {}, {}
    for uid, guidance in saved["plans"].items():
        if uid == DIAGNOSTIC_UID:
            continue
        key = "RPEval", uid
        original = wires[key]
        wire = original["actor_request"]
        if sha(wire) != original["actor_request_sha256"]:
            raise ValueError("Archived Actor request drift")
        task, memory = inputs(wire, cards[key]["root"])
        packet = proposal_wire(wire, task, memory, guidance)
        if packet is not None:
            if token_estimate(canonical(packet["messages"])) > 32768:
                raise ValueError("Recovery planner capacity exceeded")
            requests[uid, "shared"] = packet
            contexts[uid] = (guidance, memory)
    if len(requests) != 4:
        raise ValueError("Expected four eligible non-diagnostic plans")
    if action == "check":
        print(f"{len(requests)} eligible plans, maximum {len(requests)} proposal requests")
        return
    identity = {
        "experiment_sha256": sha({
            "requests": sorted((list(key), sha(value)) for key, value in requests.items()),
            "parent": sha((PARENT / "RESULTS.json").read_bytes()),
            "compiler": sha((HERE / "optional_recovery.py").read_bytes()),
        }),
        "service_reference_sha256": probe.read_reference()[1],
    }
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {STAGE: 4}
    OUT.mkdir(exist_ok=True)
    live = action == "run"
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif probe.read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Recovery proposal identity drift")
        replies = engine.stage(STAGE, requests, identity, live, ledger)
        result = {}
        for (uid, _), reply in replies.items():
            status, option = reply["status"], None
            if status == "OK":
                try:
                    option = compile_option(reply["answer"], *contexts[uid])
                    status = "OPTION" if option else "ABSTAIN"
                except (KeyError, TypeError, ValueError) as exc:
                    status = f"CONTRACT_{type(exc).__name__}"
            result[uid] = {"status": status, "option": option}

        record = {"proposals": result, "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", record)
        elif probe.read(OUT / "RESULTS.json") != record:
            raise ValueError("Recovery proposal replay differs")
        print([row["status"] for row in result.values()])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
