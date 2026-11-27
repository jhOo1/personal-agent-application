"""Resume only grading of already-frozen writer outputs."""
from collections import Counter
from execute_writers import ARMS, CAPS, RUN, graders, mag, old, roster, sha, trial


def main():
    # Historical constructors validate the historical run directory. Load them
    # before assigning the new destination to the shared stage runner.
    cards = {r["uid"]: r for r in roster()}
    multi, bench, persist = mag.cards(), old.bench_cards(), old.persist_cards()
    identity = trial.read(RUN / "WRITER_EXECUTION.json")
    assert sha(trial.read(RUN / "WRITER_FROZEN.json")) == identity["experiment_sha256"]
    assert trial.probe.read_reference()[1] == identity["service_reference_sha256"]
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = graders.RUN = mag.RUN = RUN
    trial.ARMS = graders.ARMS = mag.ARMS = ARMS
    trial.engine.CAP = CAPS
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if (RUN / "WRITER_RESULT_PRIVATE.json").exists():
            return
        saved = trial.read(RUN / "WRITER_ANSWERS_PRIVATE.json")
        outputs = saved["outputs"]
        assert set(outputs) == set(cards)
        ledger = [trial.read(p) for stage in ("BindRoles", "WriteDecision")
                  for p in sorted((RUN / stage / "visible").glob("*/record.json"))]
        assert len(ledger) == 59
        scores = mag.measure(multi, {u: outputs[u] for u in multi}, identity, ledger)
        base = {uid: row["grade"] for uid, row in multi.items()}
        for rows, evaluator in ((bench, graders.score_bench), (persist, graders.score_persist)):
            added = evaluator(rows, {k: outputs[r["uid"]] for k, r in rows.items()}, identity, ledger)
            for k, r in rows.items():
                scores[r["uid"]] = added[k]
                base[r["uid"]] = r["score"]
        trial.probe.freeze(RUN / "WRITER_LEDGER.json", ledger)
        final = {"uid_scores": {u: {"domain": cards[u]["domain"], "group": cards[u]["group"],
                                    "base": base[u], "scores": s} for u, s in scores.items()},
                 "binding": dict(Counter(saved["states"].values())), "physical_after_interface": len(ledger)}
        trial.probe.freeze(RUN / "WRITER_RESULT_PRIVATE.json", final)


if __name__ == "__main__":
    main()
