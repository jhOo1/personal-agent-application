"""Run the frozen incremental-value selector and terminal RPEval comparison."""
import argparse
from collections import Counter

from incremental_decision import selected_source
from incremental_panel import HERE, LOCAL, actor_wire, read, sha
from recovery_challenge_inputs import prepare
from recovery_supervision import demonstrations, messages
from proposals.qamc_protocol_alignment.sampling import validate_public_request
from run_probe import engine, probe

OUT = HERE / "supervised_recovery_v1"
RUN = engine.RUN.with_name("nro_supervised_recovery_v1")
SELECTOR, ACTOR = "IncrementalSelector", "IncrementalActor"
METHODS = ("ordinary", "incremental")


def put(cache, digest, answer):
    if digest in cache and cache[digest] != answer:
        raise ValueError("Conflicting exact archive receipts")
    cache[digest] = answer


def main(action):
    cards = prepare(include_archive=True)
    examples = demonstrations()
    reference = read(LOCAL / "FROZEN_ESTIMATES.json")
    template = next(target["requests"]["FULL_CONTEXT"] for row in reference["native_arms"]
                    for target in row["target_jobs"])
    jobs = {}
    for uid, card in cards.items():
        for method in METHODS:
            wire = {**template, "messages": messages(
                card["task"], card["anchor"], card["sources"], examples,
                incremental=method == "incremental")}
            validate_public_request(wire)
            jobs[uid, method] = wire
        if jobs[uid, "ordinary"]["messages"][1] != jobs[uid, "incremental"]["messages"][1]:
            raise ValueError("Unequal selector payload")
    actor_cache, judge_cache = {}, {}
    archived = read(LOCAL / "format_recovery" / "RESULTS.json")
    for row in archived["rows"]:
        if not row["selected"] or row["actor_status"] != "OK":
            continue
        put(actor_cache, row["actor_request_sha256"], row["answer"])
        judge = row.get("judge") or {}
        if judge.get("status") == "OK":
            put(judge_cache, judge["request_sha256"], judge["answer"])
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([
            sorted((list(key), sha(wire)) for key, wire in jobs.items()), cards,
            actor_cache, judge_cache, [sha((HERE / name).read_bytes()) for name in
                                     ("run_supervised_recovery.py", "recovery_challenge_inputs.py", "incremental_decision.py",
                                      "recovery_supervision.py")],
        ]),
    }
    caps = {SELECTOR: len(jobs), ACTOR: len(jobs), engine.RPE: len(jobs)}
    if action == "check":
        print(len(cards), caps, len(actor_cache), len(judge_cache))
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

        def stage(name, wires, cache=None):
            return engine.stage(name, wires, identity, live, ledger, cache) if wires else {}

        estimates = stage(SELECTOR, jobs)
        actors, rows = {}, []
        for uid, card in cards.items():
            for method in METHODS:
                key = uid, method
                receipt = estimates.get(key)
                source, status = None, "OK"
                if receipt:
                    status = receipt["status"]
                    if status == "OK":
                        try:
                            source = selected_source(receipt["answer"], card["sources"])
                        except (TypeError, ValueError):
                            status = "INVALID_SELECTOR_CONTRACT"
                if source:
                    actors[key] = actor_wire(card["root"], source)
                keep = status == "OK" and source is None
                rows.append({"uid": uid, "method": method, "group": card["group"],
                             "selected": source, "selector": receipt,
                             "actor_status": status, "answer": card["base"]["answer"] if keep else None,
                             "score": card["base"]["grade"] if keep else None,
                             "origin": "EXACT_TASK_ONLY" if keep else status})

        replies = stage(ACTOR, actors, actor_cache)
        fresh = []
        for row in rows:
            receipt = replies.get((row["uid"], row["method"]))
            if receipt:
                row.update(answer=receipt["answer"], actor_status=receipt["status"],
                           origin=receipt["origin"], actor_request_sha256=receipt["request_sha256"])
                if receipt["status"] == "OK":
                    fresh.append(row)

        def score_stage(name, wires, cache=None):
            return stage(name, wires, {**judge_cache, **(cache or {})})

        engine.grade_rpe({uid: card["root"] for uid, card in cards.items()}, fresh, score_stage)
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
