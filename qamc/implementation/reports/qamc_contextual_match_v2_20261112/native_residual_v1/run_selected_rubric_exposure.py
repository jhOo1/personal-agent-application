"""Compare two PB_RUBRIC evidence exposures with shared preparation."""
import argparse
import json

from build_jobs import archive_inputs
from check_selected_gepa_grading import grading_panel
from preflight_selected_gepa import HERE
from qamc.common import sha
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge
from replay_selected_gepa_evidence import recover, transfer
from trial_reassembly import engine, grading, probe

OUT = HERE / "selected_rubric_exposure_v1"
RUN = engine.RUN.with_name(OUT.name)
METHODS = ("SELECTED_RUBRIC", "FULL_RUBRIC_WITH_SELECTION")


def prepare():
    judge = grading_panel()
    cases = json.loads((HERE / "SELECTED_GEPA_EXPANSION_PANEL.json").read_text())["cases"]
    wires, _ = archive_inputs()
    evidence = recover()
    bridge = PersistAuthorBridge(transfer.smoke.UP)
    rubric = bridge.blobs["RUBRIC"].decode()
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
        jobs = {}
        for method, visible in zip(METHODS, (item["evidence"], memory), strict=True):
            system = bridge.render(visible, wire["model"], rubric)
            if method == METHODS[1]:
                system += "\n\nTask-relevant memories selected during preparation (advisory):\n"
                system += json.dumps(item["evidence"], ensure_ascii=False)
            jobs[method] = {**wire, "messages": [
                {"role": "system", "content": system}, wire["messages"][1],
            ]}
        selected[uid] = (case, jobs)
    return selected, judge


def run():
    selected, judge = prepare()
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = dict.fromkeys(("ExposureActor", "PersistNative"), len(selected) * len(METHODS))
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([selected, judge, engine.CAP,
                                  sha((HERE / "run_selected_rubric_exposure.py").read_bytes())]),
    }
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, True, ledger, cache) if jobs else {}

        replies = dispatch("ExposureActor", {(uid, method): wire
                                            for uid, (_, jobs) in selected.items()
                                            for method, wire in jobs.items()})
        rows = []
        for uid, (case, _) in selected.items():
            for method in METHODS:
                reply = replies[uid, method]
                rows.append({
                    "uid": uid, "method": method, "benchmark": "PersistBench",
                    "group": case["group"], "category": case["category"], "base_score": case["score"],
                    "score": None, "answer": reply.get("answer"), "actor_status": reply["status"],
                })
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    if parser.parse_args().action == "check":
        print(f"Verified {len(prepare()[0])} paired PB_RUBRIC evidence exposures")
    else:
        run()
