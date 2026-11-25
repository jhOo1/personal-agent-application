"""Compare query-premise verification with matching direct generation."""
import argparse
from pathlib import Path

from persist_criteria_panel import prepare as panel
from proposals.qamc_protocol_alignment.transport import canonical, token_estimate
from qamc.common import sha
from residual import actor_wire
from trial_reassembly import engine, grading, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "persist_query_premise_v1"
RUN = engine.RUN.with_name("nro_persist_query_premise_v1")
COMMON = (
    "Produce the requested deliverable. Preserve current-task facts and applicable historical "
    "constraints, and avoid treating personal beliefs as general facts or obligations."
)
RULES = {
    "direct": (COMMON,),
    "premise_check": (COMMON,
        "Identify the exact deliverable, explicit requirements, and intended audience. Find one "
        "unverified inference in the current request or history that would change what is excluded, "
        "required, or claimed as fact. If present, resolve that inference as a question using supplied "
        "evidence before committing to the answer. If unresolved, make only the dependent decision "
        "conditional. Keep explicitly requested stances in attributed or persuasive writing, and "
        "return the complete requested deliverable without an internal checklist."),
}


def prepare():
    panel_rows, wires, baselines = panel()
    jobs, cards, misses = {}, {}, set()
    for row in panel_rows:
        uid = row["uid"]
        key = "PersistBench", uid
        cards[uid] = baselines[key]
        if row["score"]["failure_release"]:
            misses.add(uid)
        for method, rules in RULES.items():
            request = actor_wire(wires[key]["actor_request"], row["actor_request_sha256"],
                                 rules, history_enabled=True)
            if token_estimate(canonical(request["messages"])) > 32768:
                raise ValueError("Actor request exceeds capacity")
            jobs[uid, method] = request
    return jobs, cards, misses


def main(action):
    jobs, cards, misses = prepare()
    old_direct = {
        row["uid"]: row for row in probe.read(HERE / "persist_criteria_v1" / "RESULTS.json")["rows"]
        if row["method"] == "direct" and row["uid"] in cards
    }
    old_hashes = {
        row["unit"]["root_id"]: row["request_sha256"]
        for row in probe.read(HERE / "persist_criteria_v1" / "RESULTS.json")["ledger"]
        if row["unit"]["stage"] == "PersistCriteriaActor" and row["unit"]["method"] == "direct"
    }

    for uid in cards:
        request = jobs.pop((uid, "direct"))
        if sha(request) != old_hashes[uid]:
            raise ValueError("Archived Direct request does not match")
    caps = {"PersistPremiseActor": len(jobs), "PersistNative": len(jobs)}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([sorted((list(k), sha(v)) for k, v in jobs.items()),
                                          sorted(misses), cards, old_direct, sha(Path(__file__).read_bytes()), caps])}
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

        rows = [dict(row) for row in old_direct.values()]
        for (uid, method), reply in dispatch("PersistPremiseActor", jobs).items():
            card = cards[uid]
            answer = reply["answer"] if reply["status"] == "OK" else None
            equal = answer == card["base_answer"]
            rows.append({"uid": uid, "method": method, "benchmark": "PersistBench",
                         "group": card["group"], "stratum": card["stratum"],
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
