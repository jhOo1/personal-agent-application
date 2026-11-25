"""Re-evaluate frozen content planning on other exposed profiles."""
import argparse
from pathlib import Path

from build_jobs import archive_inputs
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from residual import actor_wire
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "bench_realization_group_out_v1"
RUN = engine.RUN.with_name("nro_bench_realization_group_out_v1")
from collections import defaultdict

from run_bench_realization import OUT as PILOT, RULES


def prepare():
    wires, cards = archive_inputs()
    old = probe.read(PILOT / "RESULTS.json")
    excluded = {row["group"] for row in old["rows"]}
    remaining = defaultdict(list)
    for (benchmark, uid), card in cards.items():
        if benchmark == "BenchPreS" and card["group"] not in excluded and (benchmark, uid) in wires:
            remaining[card["group"]].append(uid)
    jobs, selected = {}, {}
    for group, uids in sorted(remaining.items()):
        for uid in sorted(uids, key=lambda item: sha(["bench-content-group-out", group, item]))[:3]:
            key = "BenchPreS", uid
            selected[uid] = cards[key]
            original = wires[key]
            for method, rules in RULES.items():
                request = actor_wire(original["actor_request"], original["actor_request_sha256"],
                                     rules, history_enabled=True)
                if token_estimate(canonical(request["messages"])) > 32768:
                    raise ValueError("Actor request exceeds capacity")
                jobs[uid, method] = request
    if not selected or len(remaining) < 2:
        raise ValueError("Insufficient disjoint exposed profiles")
    return jobs, selected


def main(action):
    jobs, cards = prepare()
    caps = {"BenchRealizationActor": len(jobs), "BenchAttrs": 6 * len(jobs)}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([sorted((list(k), sha(v)) for k, v in jobs.items()),
                                          RULES, cards, sha(Path(__file__).read_bytes()), caps])}
    if action == "check":
        print(len(cards), len({card["group"] for card in cards.values()}), caps)
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    live, ledger = action == "run", []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif probe.read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Execution identity changed")

        def dispatch(stage, batch, cache=None):
            return engine.stage(stage, batch, identity, live, ledger, cache) if batch else {}

        rows = []
        for (uid, method), reply in dispatch("BenchRealizationActor", jobs).items():
            card = cards[uid]
            answer = reply["answer"] if reply["status"] == "OK" else None
            equal = answer == card["base_answer"]
            rows.append({"uid": uid, "method": method, "benchmark": "BenchPreS",
                         "group": card["group"], "stratum": "group_out",
                         "answer": answer, "actor_status": reply["status"],
                         "origin": reply["origin"], "base_score": card["base_score"],
                         "sources": card["root"]["original_sources"],
                         "score": card["base_score"] if equal else None})
        grading(rows, dispatch)
        output = {"rows": rows, "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", output)
        elif probe.read(OUT / "RESULTS.json") != output:
            raise ValueError("Replay differs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
