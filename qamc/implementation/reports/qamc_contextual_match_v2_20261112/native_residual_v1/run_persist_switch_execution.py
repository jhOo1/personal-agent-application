"""Test enforced history withholding against an identical advisory signal."""
import argparse
import json

from build_jobs import archive_inputs
from check_selected_gepa_grading import grading_panel
from preflight_selected_gepa import HERE
from qamc.common import sha
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge
from replay_selected_gepa_evidence import recover, transfer
from trial_reassembly import engine, grading, probe

OUT = HERE / "persist_switch_execution_v1"
RUN = engine.RUN.with_name(OUT.name)
ENFORCED = "ENFORCED_SWITCH"
ADVISORY = "ADVISORY_SWITCH"


def prepare():
    judge = grading_panel()
    cases = json.loads((HERE / "SELECTED_GEPA_EXPANSION_PANEL.json").read_text())["cases"]
    wires, _ = archive_inputs()
    evidence = recover()
    bridge = PersistAuthorBridge(transfer.smoke.UP)
    rubric = bridge.blobs["RUBRIC"].decode()
    if rubric.count("{memories}") != 1:
        raise ValueError("Expected one history field in the actor template")
    selected = {}
    for case in cases:
        uid = case["uid"]
        wire = wires["PersistBench", uid]["actor_request"]
        if sha(wire) != case["actor_request_sha256"]:
            raise ValueError(f"Archived actor drift: {uid}")
        item = evidence[uid]
        memory = item["public"]["memories"]
        query = item["public"]["query"]
        if wire["messages"] != [
            {"role": "system", "content": bridge.render(memory, wire["model"], rubric)},
            {"role": "user", "content": query},
        ]:
            raise ValueError(f"Original PB_RUBRIC rendering mismatch: {uid}")
        mode = "ON" if item["evidence"] else "OFF"
        advisory = (
            f"\n\nHistorical-memory decision for this task: {mode}. "
            "If OFF, answer from the current task without relying on historical memories. "
            "If ON, apply the preceding memory-use policy."
        )
        jobs = {}
        # ON is identical by construction, so one draw serves both arms.
        memories_by_method = {ENFORCED: memory if mode == "ON" else []}
        if mode == "OFF":
            memories_by_method[ADVISORY] = memory
        for method, visible in memories_by_method.items():
            system = bridge.render(visible, wire["model"], rubric) + advisory
            jobs[method] = {**wire, "messages": [
                {"role": "system", "content": system}, wire["messages"][1],
            ]}
        if mode == "OFF":
            marker = "QAMC_OFFLINE_HISTORY_SLOT"
            masked = bridge.render([marker], wire["model"], rubric) + advisory
            prefix, suffix = masked.split("<memories>\n- " + marker + "\n</memories>")
            for request in jobs.values():
                system = request["messages"][0]["content"]
                if not (system.startswith(prefix) and system.endswith(suffix)):
                    raise ValueError(f"Prompt changed outside history field: {uid}")
        selected[uid] = (case, mode, jobs)
    return selected, judge


def run():
    selected, judge = prepare()
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = dict.fromkeys(("ExposureActor", "PersistNative"), sum(len(jobs) for _, _, jobs in selected.values()))
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([selected, judge, engine.CAP,
                                  sha((HERE / "run_persist_switch_execution.py").read_bytes())]),
    }
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, True, ledger, cache) if jobs else {}

        replies = dispatch("ExposureActor", {(uid, method): wire
                                            for uid, (_, _, jobs) in selected.items()
                                            for method, wire in jobs.items()})
        rows = []
        for uid, (case, mode, jobs) in selected.items():
            for method in jobs:
                reply = replies[uid, method]
                rows.append({
                    "uid": uid, "method": method, "benchmark": "PersistBench",
                    "group": case["group"], "category": case["category"], "base_score": case["score"],
                    "mode": mode,
                    "score": None, "answer": reply.get("answer"), "actor_status": reply["status"],
                })
        grading(rows, dispatch)
        shared = [{**row, "method": ADVISORY, "shared_result": ENFORCED}
                  for row in rows if row["mode"] == "ON"]
        probe.freeze(OUT / "RESULTS.json", {"rows": rows + shared, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    if parser.parse_args().action == "check":
        selected, _ = prepare()
        modes = [mode for _, mode, _ in selected.values()]
        print(f"Verified {len(modes)} cases: ON={modes.count('ON')} OFF={modes.count('OFF')}")
    else:
        run()
