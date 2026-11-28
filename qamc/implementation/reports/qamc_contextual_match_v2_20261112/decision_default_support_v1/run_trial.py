"""Test two same-budget policies on complete archived strong Actor inputs."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
previous = run_path(str(BASE / "strong_wire_pruning_replay_v1" / "run.py"))
archive, engine, grading, probe, sha = (previous[k] for k in ("archive", "engine", "grading", "probe", "sha"))
RUN = engine.RUN.with_name(HERE.name)
PRIVATE = RUN / "private"
PREFIX = "rpeval/formal_multi_v1/"
CASES = ("implicit/094", "implicit/142", "implicit/099", "explicit/116", "explicit/047", "explicit/006")
STAGE = "DefaultSupportActor"
ARMS = {
    "DIRECT": """Deliver the requested answer directly. Keep genuine task facts and constraints, including applicable constraints of any participant. Use personal preferences at an appropriate strength given the actual participant, recipient and task. Keep the main recommendations useful for everyone they affect and include practical alternatives when appropriate. Resolve conflicts with the current request. Do not describe your analysis or add process notes.""",
    "SUPPORTED_DEFAULT": """Before using the historical preference policy, form the leading recommendation or default on each shared decision from the current task and current facts alone. Let history change that default only if the answer can ground the change in the current shared goal, or if the history explicitly supplies a constraint for a participant affected by that choice. Keep every such binding constraint in every applicable alternative. Otherwise preserve the task-supported recommendation: a personal preference can add an independently usable option only when it leaves that recommendation available and does not impose a change on others. For a choice that affects the requester alone, use applicable preferences normally. Deliver only the usable answer, without analysis or process notes.""",
}


def prepare():
    parent = archive.read(previous["support"]["prior"]["PARENT"])
    if parent["exposed_development_only"] is not True:
        raise ValueError("Expected exposed development only")
    cards = {r["uid"]: r for r in parent["rows"] if r["uid"] in {PREFIX + case for case in CASES}}
    routes = {r["uid"]: r["old_route"] for r in archive.read(BASE / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    bank = {r["uid"]: r for r in archive.read(archive.v41.formal.OUT / "RESULT_ROWS.json")
            if r["method"] == engine.RP and r["actor_status"] == "OK" and r["uid"] in cards}
    if len(cards) != len(CASES) or len({r["group"] for r in cards.values()}) != len(CASES):
        raise ValueError("Missing or overlapping development roots")
    jobs, frozen_cases = {}, []
    for uid, card in sorted(cards.items()):
        row = bank[uid]
        wire = row["actor_request"]
        if (routes[uid] != "REUSE_RP" or sha(wire) != row["actor_request_sha256"]
                or sha(row["answer"]) != card["baseline_answer_sha256"]):
            raise ValueError("Strong input is not the archived IPE-C endpoint")
        if len(wire["messages"]) != 2 or wire["messages"][0]["role"] != "system":
            raise ValueError("Unexpected archived message layout")
        for arm, policy in sorted(ARMS.items(), key=lambda x: sha([uid, x[0]])):
            edited = deepcopy(wire)
            edited["messages"][0]["content"] += "\n\n" + policy
            jobs[uid, arm] = edited
        frozen_cases.append({"uid": uid, "stratum": card["stratum"], "group": card["group"],
                             "base_wire": sha(wire), "base_answer": card["baseline_answer_sha256"],
                             "arms": {arm: sha(jobs[uid, arm]) for arm in ARMS}})
    pin = {"cases": frozen_cases, "code": sha(Path(__file__).read_bytes()),
           "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "service_reference_sha256": probe.read_reference()[1]}
    return pin, cards, jobs


def execute(pin, cards, jobs, live):
    probe.RUN, probe.OUT, engine.OUT = RUN, PRIVATE, PRIVATE
    engine.CAP = {STAGE: 12, engine.RPE: 12}
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": pin["service_reference_sha256"]}
    ledger, reuse = [], {}

    def stage(name, wires, cache=None):
        checkpoint = PRIVATE / f"{name}_archive.json"
        if live and not checkpoint.exists():
            saved, _ = previous["support"]["prior"]["find_archived"](wires, BASE.parents[1])
            records = []
            for (uid, arm), record in saved.items():
                metadata = (BASE.parents[1] / record["archive"]).parent / "visible" / record["archive_unit"] / "record.json"
                reference = archive.read(metadata).get("reference_config_sha256") if metadata.exists() else None
                if record["status"] == "OK" and reference != pin["service_reference_sha256"]:
                    record = dict(record, status="ARCHIVED_PROTOCOL_UNVERIFIED", answer=None)
                records.append([uid, arm, record])
            probe.freeze(checkpoint, records)
        known = {(uid, arm): record for uid, arm, record in archive.read(checkpoint)}
        if any(record["request_sha256"] != sha(wires[key]) for key, record in known.items()):
            raise ValueError("Archived request mismatch")
        pending = {key: wire for key, wire in wires.items() if key not in known}
        reuse[name] = dict(Counter(r["status"] for r in known.values()))
        return known | (engine.stage(name, pending, identity, live, ledger, cache) if pending else {})

    with probe.runner_lock(RUN / "runner.lock"):
        rows = []
        for (uid, arm), actor in stage(STAGE, jobs).items():
            card = cards[uid]
            rows.append({**{key: card[key] for key in ("uid", "benchmark", "stratum", "group")},
                         "method": arm, "sources": card["packet"]["source_evidence"],
                         "actor_status": actor["status"], "answer": actor["answer"], "score": None})
        grading(rows, stage)
        result = {"rows": rows, "ledger": ledger, "exact_reuse": reuse}
        target = PRIVATE / "RESULTS.json"
        if live:
            probe.freeze(target, result)
        elif archive.read(target) != result:
            raise ValueError("Settlement replay mismatch")
        print({"physical": len(ledger), "calls": dict(Counter(r["status"] for r in ledger))})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "check", "run", "replay"))
    action = parser.parse_args().action
    data = prepare()
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    pin_path = PRIVATE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(pin_path, data[0])
    elif archive.read(pin_path) != data[0]:
        raise ValueError("Frozen comparison drift")
    if action in ("run", "replay"):
        execute(*data, live=action == "run")
    else:
        print(json.dumps({"roots": CASES, "max_new_calls": 24}))
