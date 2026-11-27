"""Run the shared ID binding, frozen writer pair, free control, and archived scorers."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

import operand_inputs as old
import operand_trial as graders
import run_matched_alternatives as mag
from interface_stage import HERE, RUN, roster, sha, text_request, trial
from writers import BINDER, FREE, WRITE, bind_input, realize, writer_views

ARMS = ("LOCAL_EDIT", "ISOLATED", "FREE")
BIND, WRITE_STAGE = "BindRoles", "WriteDecision"
CAPS = {BIND: 29, WRITE_STAGE: 87, mag.NATIVE: 36, trial.SCORE_STAGE: 3, graders.BENCH: 144, graders.PERSIST: 24}


def derive(cards, upstream, identity, ledger):
    prompts = {}
    outputs = {uid: {} for uid in cards}
    states, views = {}, {}
    for uid, row in cards.items():
        first = upstream[uid]
        if first["status"] != "OK":
            states[uid] = first["status"]
        elif not first["interface"]["decisions"]:
            states[uid] = "NO_OPEN_DECISION"
        else:
            prompts[uid, "SHARED"] = text_request(BINDER, bind_input(row, first["interface"]), "qwen3.8-flash", 8192)
    bindings = trial.stage(BIND, prompts, identity, ledger)
    jobs = {}
    for (uid, _), result in bindings.items():
        if result["status"] != "OK":
            states[uid] = result["status"]
            continue
        try:
            state, view = writer_views(cards[uid], upstream[uid]["interface"], result["answer"])
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            state, view = "INVALID_BINDING", {}
        states[uid] = state
        views[uid] = view
        for arm, payload in view.items():
            jobs[uid, arm] = text_request(FREE if arm == "FREE" else WRITE, payload, "qwen3.8-flash", 8192)
    trial.probe.freeze(RUN / "WRITER_WIRES_PRIVATE.json", {"/".join(key): wire for key, wire in jobs.items()})
    for uid in cards:
        if states[uid] == "ACT":
            continue
        fallback = states[uid] in ("NO_OPEN_DECISION", "INVALID_INTERFACE", "INVALID_BINDING", "KEEP", "UNCOVERED")
        outputs[uid] = {a: {"status": states[uid], "answer": cards[uid]["draft"] if fallback else None} for a in ARMS}
    answers_file = RUN / "WRITER_ANSWERS_PRIVATE.json"
    for (uid, arm), receipt in trial.stage(WRITE_STAGE, jobs, identity, ledger).items():
        status, answer = receipt["status"], None
        if status == "OK":
            try:
                answer = realize(cards[uid], views[uid][arm], arm, receipt["answer"])
                status = "KEEP" if answer == cards[uid]["draft"] else "EDIT"
            except (TypeError, ValueError, KeyError, AttributeError):
                status, answer = "INVALID_WRITER", cards[uid]["draft"]
        outputs[uid][arm] = {"answer": answer, "status": status, "receipt": receipt}
    trial.probe.freeze(answers_file, {"bindings": bindings_to_json(bindings), "states": states, "outputs": outputs})
    return outputs, states


def bindings_to_json(bindings):
    return {uid: value for (uid, _), value in bindings.items()}


def run(cards, first, identity):
    ledger = []
    answers, states = derive(cards, first["rows"], identity, ledger)
    multi = mag.cards()
    scores = mag.measure(multi, {uid: answers[uid] for uid in multi}, identity, ledger)
    base = {uid: row["grade"] for uid, row in multi.items()}
    for rows, evaluator in ((old.bench_cards(), graders.score_bench), (old.persist_cards(), graders.score_persist)):
        added = evaluator(rows, {name: answers[c["uid"]] for name, c in rows.items()}, identity, ledger)
        for name, row in rows.items():
            scores[row["uid"]] = added[name]
            base[row["uid"]] = row["score"]
    trial.probe.freeze(RUN / "WRITER_LEDGER.json", ledger)
    final = {"uid_scores": {uid: {"domain": cards[uid]["domain"], "group": cards[uid]["group"],
                                   "base": base[uid], "scores": x} for uid, x in scores.items()},
             "binding": dict(Counter(states.values())), "physical_after_interface": len(ledger)}
    trial.probe.freeze(RUN / "WRITER_RESULT_PRIVATE.json", final)
    print(final["binding"], "post-interface requests", len(ledger))


def main(command):
    cards = {row["uid"]: row for row in roster()}
    first_lock = trial.read(RUN / "INTERFACE_FROZEN.json")
    pin = {"interface": sha(first_lock), "code": {n: sha((HERE / n).read_bytes()) for n in
           ("execute_writers.py", "execute_writers.sh", "writers.py", "PROTOCOL.md")},
           "caps": CAPS, "arms": list(ARMS)}
    trial.RUN = trial.engine.OUT = trial.probe.OUT = trial.probe.RUN = graders.RUN = mag.RUN = RUN
    trial.ARMS = graders.ARMS = mag.ARMS = ARMS
    trial.engine.CAP = CAPS
    if command == "freeze":
        trial.probe.freeze(RUN / "WRITER_FROZEN.json", pin)
        print("Writer contract frozen for", len(cards), "development tasks")
        return
    with trial.probe.runner_lock(RUN / "runner.lock"):
        if trial.read(RUN / "WRITER_FROZEN.json") != pin:
            raise ValueError("Writer contract changed")
        first = trial.read(RUN / "INTERFACES_PRIVATE.json")
        service = trial.probe.read_reference()[1]
        if first["identity"] != {"experiment_sha256": sha(first_lock), "service_reference_sha256": service}:
            raise ValueError("Interface receipts or service changed")
        if (RUN / "WRITER_RESULT_PRIVATE.json").exists():
            print("Already settled")
            return
        identity = {"experiment_sha256": sha(pin), "service_reference_sha256": service}
        trial.probe.freeze(RUN / "WRITER_EXECUTION.json", identity)
        run(cards, first, identity)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("command", choices=("freeze", "run"))
    main(parser.parse_args().command)
