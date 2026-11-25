"""Run speaker-aware lexical extraction on the projection cohort."""
import argparse
import json
import re

from run_hidden_b_oracle import prepare as oracle
from run_source_projection_diagnostic import prepare as projected
from rpe_source_projection import project
from incremental_panel import HERE, read, sha
from run_probe import engine, probe

OUT = HERE / "source_projection_speaker_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "SpeakerActor"


def prepare():
    whole, _, roots = oracle()
    treatments, cards, _ = projected()
    jobs = {}
    for (uid, _), wire in whole.items():
        packet = json.loads(wire["messages"][1]["content"])
        source, = packet["source_evidence"]
        treatment = json.loads(treatments[uid, "projection"]["messages"][1]["content"])
        budget = len(treatment["source_evidence"][0]["text"])
        query_chars = set(packet["query"])
        text = source["text"]
        turns = list(re.finditer(r"(?m)^(用户|助手)：", text))
        candidates = []
        for i, turn in enumerate(turns):
            if turn[1] != "用户":
                continue
            end = turns[i + 1].start() if i + 1 < len(turns) else len(text)
            for sentence in re.finditer(r"[^。！？\n]+[。！？]", text[turn.end():end]):
                if 0.8 * budget <= len(sentence[0]) <= 1.2 * budget:
                    candidates.append((sentence, turn.end()))
        if not candidates:
            raise ValueError("No user sentence within the frozen character window")
        best, offset = max(candidates, key=lambda item: (
            len(query_chars.intersection(item[0][0])),
            -abs(len(item[0][0]) - budget), -item[1] - item[0].start(),
        ))
        candidate = project(wire, sha(wire), source["memory_id"],
                            [(offset + best.start(), offset + best.end())])
        if candidate != treatments[uid, "projection"]:
            jobs[uid, "speaker"] = candidate
    if len(jobs) != 2:
        raise ValueError("Expected two nonidentical requests")
    return jobs, cards, roots


def main(check):
    jobs, cards, roots = prepare()
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([
            cards, sorted((list(key), sha(wire)) for key, wire in jobs.items()),
            sha((HERE / "run_source_projection_speaker.py").read_bytes()),
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
             "answer": response.get("answer"), "base_score": cards[uid]["base_score"], "whole_score": cards[uid]["score"], "score": None}
            for (uid, method), response in dispatch(STAGE, jobs).items()
        ]
        engine.grade_rpe(roots, rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    main(parser.parse_args().action == "check")
