"""Draw a contemporaneous B control on the frozen promotion cohort."""
import argparse

from run_visible_c_promotion import prepare as promotion, OUT as PROMOTION
from incremental_panel import HERE, prior, read, sha
from run_probe import engine, probe

OUT = HERE / "visible_c_b_control_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "VisibleBControl"


def prepare():
    promoted, cards, roots = promotion()
    frozen = read(PROMOTION / "VisibleCActor_MANIFEST.json")["units"]
    if {row["unit"]["root_id"]: sha(row["request"]) for row in frozen} != {
        uid: sha(wire) for (uid, _), wire in promoted.items()
    }:
        raise ValueError("Promotion cohort or requests changed")
    v41 = prior.R["archived"].v41
    originals = {row["uid"]: row for row in read(v41.formal.OUT / "RESULT_ROWS.json")
                 if row["method"] == "RPR_PAPER_FULL" and row["uid"] in cards}
    jobs = {}
    for uid in cards:
        row = originals[uid]
        wire = row["actor_request"]
        if sha(wire) != row["actor_request_sha256"]:
            raise ValueError("B control request changed")
        jobs[uid, "b_control"] = wire
    return jobs, cards, roots


def main(check):
    jobs, cards, roots = prepare()
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([
            cards, sorted((list(key), sha(wire)) for key, wire in jobs.items()),
            sha((HERE / "run_visible_b_control.py").read_bytes()),
        ]),
    }
    if check:
        print(f"{len(jobs)} eligible Actor requests; {identity['experiment_sha256']}")
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, {STAGE: len(jobs), engine.RPE: len(jobs)}
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, wires, cache=None):
            return engine.stage(stage, wires, identity, True, ledger, cache) if wires else {}

        rows = [
            {"uid": uid, "method": method, "actor_status": response["status"],
             "answer": response.get("answer"), "base_score": cards[uid]["base_scores"], "score": None}
            for (uid, method), response in dispatch(STAGE, jobs).items()
        ]
        engine.grade_rpe(roots, rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    main(parser.parse_args().action == "check")
