"""Run or replay the predeclared search-only NRO transport pilot."""
import argparse
from pathlib import Path

from build_jobs import prepare
from evaluate_nro_policy import evaluate
from qamc.common import sha
from trial_reassembly import engine, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "pilot_v1"
RUN = engine.RUN.with_name("native_residual_pilot_v1")
RULES = (
    "Use historical preferences only for decisions they can legitimately shape in this task; "
    "keep explicit requirements and provide a complete usable answer.",
)


def main(action):
    engine.OUT = probe.OUT = OUT
    probe.RUN = RUN
    arm = "nro_" + sha(RULES)[:24]
    caps = {
        "RPEval_Actor": 6, "BenchPreS_Actor": 4, "PersistBench_Actor": 7,
        "RPEvalJudge": 6, "BenchAttrs": 24, "PersistNative": 7,
    }
    engine.CAP = {f"{arm}_{stage}": cap for stage, cap in caps.items()}
    jobs, _ = prepare(RULES, "search")
    plan = {
        "experiment_sha256": sha({
            "actor_wires": sorted((list(key), sha(wire)) for key, wire in jobs.items()),
            "rules": RULES, "caps": caps, "roster": sha((HERE / "ROSTER.json").read_bytes()),
            "code": {name: sha((HERE / name).read_bytes()) for name in (
                "build_jobs.py", "evaluate_nro_policy.py", "freeze_roster.py", "residual.py",
                "run_nro_pilot.py")},
        }),
        "service_reference_sha256": probe.read_reference()[1],
    }
    if action == "check":
        print(f"Actor jobs: {len(jobs)}; physical request cap: {sum(caps.values())}")
        return

    OUT.mkdir(exist_ok=True)
    ledger = []
    live = action == "run"
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", plan)
        elif probe.read(OUT / "EXECUTION.json") != plan:
            raise ValueError("Frozen execution identity changed")

        def dispatch(stage, requests, cache=None):
            return engine.stage(stage, requests, plan, live, ledger, cache) if requests else {}

        rows = evaluate(RULES, "search", dispatch)
        results = {"rows": rows, "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", results)
        elif probe.read(OUT / "RESULTS.json") != results:
            raise ValueError("Saved pilot results differ from replay")
        print(f"Rows: {len(rows)}; requests in ledger: {len(ledger)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
