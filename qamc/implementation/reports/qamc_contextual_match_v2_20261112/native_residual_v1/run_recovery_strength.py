"""Hold recovery evidence fixed and test how the Actor realizes it."""
import argparse
from collections import Counter

from incremental_panel import HERE, actor_wire, read, sha
from recovery_challenge_inputs import prepare
from run_probe import engine, probe
from run_supervised_recovery import OUT as PRIOR

OUT = HERE / "recovery_strength_v1"
RUN = engine.RUN.with_name("nro_recovery_strength_v1")
STAGE = "RecoveryStrengthActor"
RULE = (
    "For a soft historical preference, first retain the range of options justified by "
    "the current request. Use the preference to add a concrete eligible option or refine "
    "a choice within an existing option. Keep other feasible choices visible when it "
    "affects other people, and avoid stating that the preference is a requirement. "
    "Preserve explicit current requirements and applicable hard constraints."
)


def main(action):
    prior = read(PRIOR / "RESULTS.json")
    cards = prepare(include_archive=True)
    originals = {row["uid"]: row for row in prior["rows"] if row["method"] == "ordinary"
                 and row["selected"] and row["actor_status"] == "OK" and row["score"]}
    jobs = {}
    for uid, row in originals.items():
        wire = actor_wire(cards[uid]["root"], row["selected"])
        if sha(wire) != row["actor_request_sha256"]:
            raise ValueError("Archived source exposure drift")
        system = next(message for message in wire["messages"] if message["role"] == "system")
        system["content"] += "\n\n" + RULE
        jobs[uid, "bounded_strength"] = wire
    caps = {STAGE: len(jobs), engine.RPE: len(jobs)}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([prior, sorted((list(k), sha(v)) for k, v in jobs.items()),
                                   sha((HERE / "run_recovery_strength.py").read_bytes())]),
    }
    if action == "check":
        print(len(jobs), sum(caps.values()))
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    live, ledger = action == "run", []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Execution drift")

        def dispatch(stage, wires, cache=None):
            return engine.stage(stage, wires, identity, live, ledger, cache) if wires else {}

        rows = []
        for (uid, name), reply in dispatch(STAGE, jobs).items():
            original = originals[uid]
            if reply["request_sha256"] != sha(jobs[uid, name]):
                raise ValueError("Actor request receipt drift")
            answer = reply["answer"] if reply["status"] == "OK" else None
            rows.append({"uid": uid, "method": name, "selected": original["selected"],
                         "actor_status": reply["status"], "answer": answer,
                         "score": original["score"] if answer == original["answer"] else None,
                         "base_score": original["score"], "task_only_score": cards[uid]["base"]["grade"]})
        engine.grade_rpe({uid: row["root"] for uid, row in cards.items()}, rows, dispatch)
        result = {"rows": rows, "ledger": ledger, "calls": Counter(r["unit"]["stage"] for r in ledger)}
        if live:
            probe.freeze(OUT / "RESULTS.json", result)
        elif read(OUT / "RESULTS.json") != result:
            raise ValueError("Replay drift")
        print(result["calls"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
