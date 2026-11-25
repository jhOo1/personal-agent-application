"""Evaluate source removal using the previously scored scoped arm as control."""
import argparse
from pathlib import Path

from build_jobs import archive_inputs, prepare
from qamc.common import sha
from run_scope_pilot import OUT as PARENT
from scope_visibility import restricted_wire
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "scope_visibility_v1"
RUN = engine.RUN.with_name(OUT.name)


def main(action):
    saved = probe.read(PARENT / "RESULTS.json")
    controls = {row["uid"]: row for row in saved["rows"] if row["method"] == "scoped"}
    archived, _ = archive_inputs()
    _, base = prepare((), "search")
    jobs, removed = {}, {}
    for uid, guidance in saved["plans"].items():
        original = archived["RPEval", uid]
        wire = original["actor_request"]
        if sha(wire) != original["actor_request_sha256"]:
            raise ValueError("Archive drift")
        request, removed[uid] = restricted_wire(wire, guidance, controls[uid]["sources"])
        if removed[uid]:
            jobs[uid, "restricted"] = request
    if len(controls) != 6 or len(jobs) != 5:
        raise ValueError("Unexpected coverage of saved guidance")
    if action == "check":
        print("6 controls; 5 new Actor jobs; at most 5 grades")
        return

    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha({
            "wires": sorted((list(k), sha(v)) for k, v in jobs.items()),
            "parent": sha((PARENT / "RESULTS.json").read_bytes()),
            "code": sha(Path(__file__).read_bytes()),
        }),
    }
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    engine.CAP = {"RestrictedActor": 5, engine.RPE: 5}
    OUT.mkdir(exist_ok=True)
    ledger = []
    live = action == "run"
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif probe.read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Visibility execution identity drift")

        def dispatch(stage, requests, cache=None):
            return engine.stage(stage, requests, identity, live, ledger, cache) if requests else {}

        replies = dispatch("RestrictedActor", jobs)
        rows = []
        for uid, control in controls.items():
            if not removed[uid]:
                rows.append({**control, "method": "restricted"})
                continue
            reply = replies[uid, "restricted"]
            status = reply["status"]
            answer = reply["answer"] if status == "OK" else None
            card = base["RPEval", uid]
            score = flags = None
            if answer == control["answer"]:
                score, flags = control["score"], control["score_flags"]
            elif answer == card["base_answer"]:
                score, flags = card["base_score"], card["base_flags"]
            rows.append({**{k: control[k] for k in ("uid", "benchmark", "group", "stratum", "sources")},
                         "method": "restricted", "actor_status": status, "answer": answer,
                         "score": score, "score_flags": flags})
        grading(rows, dispatch)
        result = {"rows": rows, "removed_sources": removed, "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", result)
        elif probe.read(OUT / "RESULTS.json") != result:
            raise ValueError("Visibility result differs from replay")
        print(f"Rows: {len(rows)}; recorded requests: {len(ledger)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
