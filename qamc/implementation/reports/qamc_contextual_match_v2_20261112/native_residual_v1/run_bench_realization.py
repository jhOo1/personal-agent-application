"""Compare first-pass content planning with matched direct generation."""
import argparse
from pathlib import Path

from build_jobs import archive_inputs
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from residual import actor_wire
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "bench_realization_v1"
RUN = engine.RUN.with_name("nro_bench_realization_v1")
COMMON = ("Preserve all supported task facts and requested actions. Apply only style preferences "
          "appropriate to the current recipient and deliverable. Output only the requested message.")
RULES = {
    "direct": (COMMON,),
    "content_first": (COMMON, "Before composing, silently list the factual propositions and requested "
                      "speech acts. Then realize the appropriate style over that list. Compression may "
                      "merge propositions but must preserve their meaning and all requested actions.",),
}


def prepare():
    wires, cards = archive_inputs()
    census = probe.read(HERE.parent / "strong_actor_boundary_audit_v1" / "CENSUS.json")
    attributes = census["BenchPreS"]["attributes"]
    misses = {row["uid"]: row for row in attributes
              if row["expression"] == "SELECTED_EXACT" and row["base_follow"] != "follow"}
    controls = {}
    for row in sorted(attributes, key=lambda r: sha(r["uid"])):
        profile = row["profile_group"]
        if (row["base_follow"] == "follow" and row["expression"] == "SELECTED_EXACT"
                and row["uid"] not in misses and profile in {v["profile_group"] for v in misses.values()}
                and ("BenchPreS", row["uid"]) in wires):
            controls.setdefault(profile, row)
    pool = {**misses, **{row["uid"]: row for row in controls.values()}}
    if len(misses) != 9 or len(controls) != 3:
        raise ValueError("Unexpected census coverage")
    jobs = {}
    for uid, evidence in pool.items():
        original = wires["BenchPreS", uid]
        if sha(original["answer"]) != evidence["answer_sha256"]:
            raise ValueError("Census answer differs")
        for method, rules in RULES.items():
            request = actor_wire(original["actor_request"], evidence["actor_request_sha256"],
                                 rules, history_enabled=True)
            if token_estimate(canonical(request["messages"])) > 32768:
                raise ValueError("Actor request exceeds capacity")
            jobs[uid, method] = request
    return jobs, {uid: cards["BenchPreS", uid] for uid in pool}, set(misses)


def main(action):
    jobs, cards, misses = prepare()
    caps = {"BenchRealizationActor": len(jobs), "BenchAttrs": 6 * len(jobs)}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([sorted((list(k), sha(v)) for k, v in jobs.items()),
                                          sorted(misses), cards, sha(Path(__file__).read_bytes()), caps])}
    if action == "check":
        print(len(cards), len(misses), caps)
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
                         "group": card["group"], "stratum": "delivered_miss" if uid in misses else "protection",
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
