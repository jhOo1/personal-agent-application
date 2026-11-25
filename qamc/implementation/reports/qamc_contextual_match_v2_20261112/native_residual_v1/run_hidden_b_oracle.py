"""Run a development-only single-source oracle on unmatched hidden B cases."""
import argparse

from audit_hidden_b_misses import bounds
from incremental_panel import HERE, actor_wire, prior, read, sha
from run_probe import engine, probe

OUT = HERE / "hidden_b_oracle_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "HiddenBActor"


def prepare():
    census = read(HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json")["RPEval"]["roots"]
    archives = [
        HERE.parent / "source_local_reentry_v1" / "format_recovery" / "RESULTS.json",
        *(HERE / folder / "RESULTS.json" for folder in (
            "supervised_recovery_v1", "incremental_pair_v1", "recovery_strength_v1",
        )),
    ]
    used = {(r["uid"], r["selected"]) for path in archives for r in read(path)["rows"]
            if isinstance(r.get("selected"), str) and r.get("score")}
    v41 = prior.R["archived"].v41
    frozen = read(v41.OUT / "FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Expected exposed development data")
    roots = {r["uid"]: r for r in frozen["roots"]}
    jobs, cards = {}, {}
    for row in census:
        ids = [p["id"] for p in row["positions"] if p["author_label"] == "B" and p["state"] == "HIDDEN"]
        if len(ids) != 1 or bounds(row) != (1, 1) or (row["uid"], ids[0]) in used:
            continue
        uid = row["uid"]
        jobs[uid, "oracle_b"] = actor_wire(roots[uid], ids[0])
        cards[uid] = row
    if len(jobs) != 3 or len({r["group"] for r in cards.values()}) != 3:
        raise ValueError("Unexpected diagnostic cohort")
    return jobs, cards, {uid: roots[uid] for uid in cards}


def main(check):
    jobs, cards, roots = prepare()
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([
            cards, sorted((list(key), sha(wire)) for key, wire in jobs.items()),
            sha((HERE / "run_hidden_b_oracle.py").read_bytes()),
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
