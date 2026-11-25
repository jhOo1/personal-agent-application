"""Measure a fresh PB_RUBRIC draw on the frozen expansion panel."""
import argparse
import json

from build_jobs import archive_inputs
from check_selected_gepa_grading import grading_panel
from preflight_selected_gepa import HERE
from qamc.common import sha
from trial_reassembly import engine, grading, probe

OUT = HERE / "selected_gepa_pb_rubric_resample_v1"
RUN = engine.RUN.with_name(OUT.name)
METHOD = "PB_RUBRIC_RESAMPLE"


def prepare():
    judge = grading_panel()
    cases = json.loads((HERE / "SELECTED_GEPA_EXPANSION_PANEL.json").read_text())["cases"]
    wires, _ = archive_inputs()
    selected = {}
    for case in cases:
        uid = case["uid"]
        wire = wires["PersistBench", uid]["actor_request"]
        if sha(wire) != case["actor_request_sha256"]:
            raise ValueError(f"Archived actor drift: {uid}")
        selected[uid] = (case, wire)
    return selected, judge


def run():
    selected, judge = prepare()
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = dict.fromkeys(("ResampleActor", "PersistNative"), len(selected))
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([selected, judge, engine.CAP,
                                  sha((HERE / "run_selected_gepa_resample.py").read_bytes())]),
    }
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, True, ledger, cache) if jobs else {}

        replies = dispatch("ResampleActor", {(uid, METHOD): wire
                                            for uid, (_, wire) in selected.items()})
        rows = []
        for uid, (case, _) in selected.items():
            reply = replies[uid, METHOD]
            rows.append({
                "uid": uid, "method": METHOD, "benchmark": "PersistBench",
                "group": case["group"], "category": case["category"], "base_score": case["score"],
                "score": None, "answer": reply.get("answer"), "actor_status": reply["status"],
            })
        grading(rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    if parser.parse_args().action == "check":
        print(f"Verified {len(prepare()[0])} exact PB_RUBRIC Actor wires")
    else:
        run()
