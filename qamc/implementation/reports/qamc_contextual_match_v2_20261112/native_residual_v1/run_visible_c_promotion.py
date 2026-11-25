"""Test a single B-to-C policy promotion on exposed RPEval roots."""
import argparse

from rpe_policy_promotion import promote
from incremental_panel import HERE, prior, read, sha
from run_probe import engine, probe

OUT = HERE / "visible_c_promotion_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "VisibleCActor"


def prepare():
    census = read(HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json")["RPEval"]["roots"]
    v41 = prior.R["archived"].v41
    frozen = read(v41.OUT / "FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Expected exposed development data")
    roots = {r["uid"]: r for r in frozen["roots"]}
    originals = {r["uid"]: r for r in read(v41.formal.OUT / "RESULT_ROWS.json")
                 if r["method"] == "RPR_PAPER_FULL" and r["uid"] in roots}
    jobs, cards, groups = {}, {}, set()
    for row in sorted(census, key=lambda entry: sha(["visible_c_promotion_v1", entry["uid"]])):
        ids = [p["id"] for p in row["positions"]
               if p["author_label"] == "C" and p["state"] == "VISIBLE_B"]
        baseline = row["base_scores"]
        if (not ids or row["group"] in groups or baseline["flags"]
                or baseline["matched"] == len(row["positions"])):
            continue
        uid = row["uid"]
        original = originals[uid]
        if sha(original["answer"].strip()) != baseline["answer_sha256"]:
            raise ValueError("Baseline answer drift")
        jobs[uid, "promote_c"] = promote(original["actor_request"],
                                         original["actor_request_sha256"], ids[0])
        cards[uid] = row
        groups.add(row["group"])
        if len(groups) == 8:
            break
    if len(groups) != 8:
        raise ValueError("Expected eight exposed source groups")
    return jobs, cards, {uid: roots[uid] for uid in cards}


def main(check):
    jobs, cards, roots = prepare()
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([
            cards, sorted((list(key), sha(wire)) for key, wire in jobs.items()),
            sha((HERE / "run_visible_c_promotion.py").read_bytes()),
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
