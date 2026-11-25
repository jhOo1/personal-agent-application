"""Evaluate the previously unissued Actor request after a lossless format repair."""
import argparse
import json
from pathlib import Path

import qamc_paper_baseline_validation_run as old
from trial_reassembly import archive, engine, probe

HERE = Path(__file__).resolve().parent
OUT = HERE / "bench_format_recovery_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "RecoveredBenchActor"
EXPECTED = "a6d92e3b2cb0c2b107e5421cfe3f489da1a576855a1fc28c3ed7b82b2ebd1310"


def prepare():
    row, = [r for r in old.read(old.OUT / "RESULT_ROWS.json")
            if r["method"] == engine.GATE and r["uid"].startswith("benchpres/")
            and r["uid"].split("/")[-1].startswith("dd0701a4")]
    if row["actor_status"] != "NOT_ISSUED" or row["read_status"] != "INVALID_CONTRACT":
        raise ValueError("Original recovery case drift")
    task = old.task_for(row)
    data = json.loads(row["selector_answer"])
    entry, = [item for item in data["preference_actions"] if set(item) > {"memory_id", "decision"}]
    source, = [item for item in task.memories if item.memory_id == entry["memory_id"]]
    if entry["decision"] != "APPLY" or entry["text"] != source.text or list(entry["spans"].values()) != [source.text]:
        raise ValueError("Proposed repair is not a redundant-field removal")
    del entry["text"]
    del entry["spans"]
    compiled = old.actor(task, json.dumps(data), row["method"], old.read(old.OUT / "PROMPTS.json")["base"],
                         old.PersistAuthorBridge(old.previous.parent.AUTHOR))
    wire = compiled["request"]
    if old.sha(wire) != EXPECTED:
        raise ValueError("Recovered Actor wire differs from audited digest")
    return row["uid"], wire


def main(action):
    uid, wire = prepare()
    if action == "check":
        print("One previously unissued Actor request, at most six grades")
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, {STAGE: 1, "BenchAttrs": 6}
    OUT.mkdir(exist_ok=True)
    live, ledger = action == "run", []
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": old.sha([wire, (HERE / Path(__file__).name).read_text()])}
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(OUT / "EXECUTION.json", identity)
        elif probe.read(OUT / "EXECUTION.json") != identity:
            raise ValueError("Execution drift")

        def dispatch(stage, jobs, cache=None):
            return engine.stage(stage, jobs, identity, live, ledger, cache) if jobs else {}

        method = "FORMAT_RECOVERED_GATE"
        reply = dispatch(STAGE, {(uid, method): wire})[uid, method]
        root, = [item for item in archive.transfer.development_roots("BenchPreS") if item["uid"] == uid]
        row = {"uid": uid, "method": method, "benchmark": "BenchPreS",
               "actor_status": reply["status"], "answer": reply["answer"],
               "score": None, "sources": root["original_sources"]}
        from trial_reassembly import grading
        grading([row], dispatch)
        result = {"rows": [row], "ledger": ledger}
        if live:
            probe.freeze(OUT / "RESULTS.json", result)
        elif probe.read(OUT / "RESULTS.json") != result:
            raise ValueError("Replay drift")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run", "replay"))
    main(parser.parse_args().action)
