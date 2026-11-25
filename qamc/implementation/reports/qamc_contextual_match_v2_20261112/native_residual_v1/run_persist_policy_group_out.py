"""Freeze search-side policy choices and evaluate separate exposed source groups."""
import argparse
import json

from build_jobs import archive_inputs
from run_persist_policy_adapt import OUT as ADAPT, prior_round
from freeze_persist_policy_panel import OUT as PANEL, build
from persist_policy_block import locate, policy_wire
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha
from trial_reassembly import engine, grading, probe

OUT = PANEL.parent / "persist_policy_group_out_v1"
RUN = engine.RUN.with_name(OUT.name)


def prepare():
    panel = probe.read(PANEL)
    if panel != build():
        raise ValueError("Panel drift")
    wires, cards = archive_inputs()
    search = {}
    for row in panel["rows"]:
        if row["split"] != "group_out":
            continue
        key = "PersistBench", row["uid"]
        search[row["uid"]] = wires[key]["actor_request"], cards[key]
    return panel, search


def run(check):
    panel, search = prepare()
    rounds = [prior_round(), probe.read(ADAPT / "RESULTS.json")]
    search_ids = {row["uid"] for row in panel["rows"] if row["split"] == "search"}
    if any(row["uid"] not in search_ids for result in rounds for row in result["rows"]):
        raise ValueError("Unexpected selection data")
    choices = {}
    for mode in ("append", "replace"):
        candidates = []
        for index, result in enumerate(rounds):
            rows = [row for row in result["rows"] if row["method"] == mode]
            if mode not in result["policies"]:
                continue
            if {row["uid"] for row in rows} != search_ids or len(rows) != len(search_ids):
                raise ValueError("Incomplete strategy row inventory")
            known = [row for row in rows if type((row["score"] or {}).get("failure_release")) is bool]
            protected_losses = sum(
                row["stratum"] != "sycophancy" and not row["base_score"]["failure_release"]
                and (row["score"] or {}).get("failure_release") is not False for row in rows
            )
            passes = sum(not row["score"]["failure_release"] for row in known)
            candidates.append(((-protected_losses, passes, len(known), -index), index))
        if not candidates:
            raise ValueError("No changed strategy to compare")
        choices[mode] = max(candidates)[1]
    policies = {mode: rounds[index]["policies"][mode] for mode, index in choices.items()}
    jobs = {(uid, mode): policy_wire(wire, sha(wire), mutation, mode,
                                      byte_cap=panel["byte_cap"])
            for uid, (wire, _) in search.items() for mode, mutation in policies.items()}
    for wire in jobs.values():
        validate_public_request(wire)
    caps = {"PolicyActor": len(jobs), "PersistNative": len(jobs)}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([panel, choices, sorted((list(key), sha(wire)) for key, wire in jobs.items()), caps, sha(__file_bytes())]),
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
        probe.freeze(OUT / "SELECTION.json", {"round_indices": choices, "policy_hashes": {m: sha(t) for m, t in policies.items()}})

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
            "rows": rows, "ledger": ledger, "policy_hashes": {m: sha(t) for m, t in policies.items()}, "round_indices": choices,
        })


def __file_bytes():
    return PANEL.with_name("run_persist_policy_group_out.py").read_bytes()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    run(parser.parse_args().action == "check")
