"""Compare direct and enforced rendering of exactly the same complete model response."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import outcome_contract as method
import run_decision_replacement as parent
from settle_joint_planning import score_matrix, usage


OUT, RUN = parent.OUT.with_name("outcome_contract_rpeval_v1"), parent.RUN.with_name("outcome_contract_rpeval_v1")
CONTRACT, ACTOR, JUDGE = "OutcomeContract", "OutcomeAnswer", parent.JUDGE
GENERIC, ATOMIC, GATE, RP = parent.CONTROLS
CONTROLS = (GENERIC, ATOMIC, GATE, RP)
probe, read, replay = parent.probe, parent.read, parent.replay


def prepare():
    initial, _, roots, history, data, inherited = parent.prepare()
    old, _, cases = data
    cache = {CONTRACT: {}, ACTOR: {}, JUDGE: dict(inherited[JUDGE])}
    for base in (parent.OUT, parent.OUT / "framing_recovery"):
        if read(base / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Prior runs must be settled before reusing their receipts")
        cache[JUDGE].update(read(base / f"{JUDGE}_EXACT.json"))
    jobs = [(uid, "SHARED", method.contract_request(roots[uid], state["contract"])) for uid, state in history.items()]
    if len(jobs) != 55 or old.keys() != history.keys() or not history.keys() <= cases.keys():
        raise ValueError("Exposed cohort does not match the frozen 55 histories")
    paths = (Path(__file__), Path(method.__file__), Path(parent.__file__),
             Path(__file__).with_name("OUTCOME_CONTRACT_PROTOCOL.md"))
    spec = {"panel": "pilot", "caps": {CONTRACT: 55, ACTOR: 55, JUDGE: 110},
            "wire_sha256": {uid: sha(wire) for uid, _, wire in jobs},
            "source_groups": len({r["group"] for r in old.values()}),
            "service_reference_sha256": initial["service_reference_sha256"], "previous_spec_sha256": sha(initial),
            "judge_cache_sha256": sha(cache[JUDGE]), "code_sha256": {p.name: sha(p.read_bytes()) for p in paths},
            "independent_confirmation": False, "automatic_retries": 0,
            "screen": {"coverage": .90, "min_changed_groups": 2, "severity_margin": .10}}
    return spec, jobs, roots, history, data, cache


def evaluate(inputs, stage):
    _, jobs, roots, history, (rows, official, cases), _ = inputs
    contracts, actors, scores = {}, [], []
    results = stage(CONTRACT, jobs)
    for uid, key, wire in jobs:
        record, raw = results[uid, key]
        trace = {"status": record["status"], "request_sha256": sha(wire)}
        contracts[uid] = trace
        row = rows[uid]
        row["outputs"] = {}
        if trace["status"] == "OK":
            try:
                state = history[uid]
                uses, rejected = method.compile_uses(roots[uid], state["contract"], raw)
                trace.update(uses=uses, rejected=rejected)
                if uses:
                    actors.append((uid, key, method.actor_request(roots[uid], state["contract"], uses, state["draft"])))
                else:
                    row["outputs"] = dict.fromkeys(method.ARMS, state["draft"])
            except (KeyError, TypeError, ValueError):
                trace["status"] = "INVALID_OUTCOME_CONTRACT"
        row["actor"] = {"status": trace["status"] if trace["status"] != "OK" else "UNISSUED"}
        if row["outputs"]:
            row["actor"]["status"] = "SHARED_TASK_ONLY_DRAFT"
        row["native"].update({arm: {"status": row["actor"]["status"], "fields": {}} for arm in method.ARMS})
        for arm, answer in row["outputs"].items():
            scores.append((uid, arm, parent.SCORER.grade_request(official, cases[uid], answer)))
    actor_results = stage(ACTOR, actors)
    for uid, key, wire in actors:
        record, raw = actor_results[uid, key]
        row = rows[uid]
        actor = {"status": record["status"], "request_sha256": sha(wire)}
        row["actor"] = actor
        if actor["status"] == "OK":
            try:
                answers, audit = method.compile_answer(raw, history[uid]["contract"], contracts[uid]["uses"],
                                                       roots[uid]["public_task"]["query"])
                actor["structure"] = audit
                row["outputs"] = {k: v for k, v in answers.items() if v is not None}
            except (KeyError, TypeError, ValueError):
                actor["status"] = "INVALID_OUTCOME_ITEMS"
        for arm in method.ARMS:
            status = "GUARD_SCOPE_UNCOVERED" if actor["status"] == "OK" and arm not in row["outputs"] else actor["status"]
            row["native"][arm] = {"status": status, "fields": {}}
            if arm in row["outputs"]:
                wire = parent.SCORER.grade_request(official, cases[uid], row["outputs"][arm])
                scores.append((uid, arm, wire))
    for (uid, arm), (record, raw) in stage(JUDGE, scores).items():
        rows[uid]["native"][arm] = parent.SCORER.parse_grade(record, raw, rows[uid]["positions"])
    return contracts, list(rows.values())


def summarize(spec, contracts, rows, ledger):
    plain, enforced = method.ARMS
    compare = parent.SCORER.comparisons.grade_pair
    panels = {"all": rows, "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
              "B_only": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
              "contains_C": [r for r in rows if "C" in r["labels"]],
              "guard_predicted": [r for r in rows if any(u["force"] == "REQUIRE"
                                                       for u in contracts[r["uid"]].get("uses", []))]}
    paired = {name: {arm: {"match": replay.paired(sample, arm, enforced),
                           **{f: compare(sample, arm, enforced, f) for f in ("OPB", "UPB", "FM", "VG")}}
                     for arm in (plain, *CONTROLS)} for name, sample in panels.items()}
    active_changes = [r for r in rows if len(r["outputs"]) == 2 and r["outputs"][plain] != r["outputs"][enforced]]
    withheld = [r["uid"] for r in rows if plain in r["outputs"] and enforced not in r["outputs"]]
    gates = {"changed_two_groups": len({r["group"] for r in active_changes}) >= spec["screen"]["min_changed_groups"]}
    for arm in (plain, GENERIC, GATE, RP):
        for name in ("all", "all_A", "B_only", "contains_C"):
            match = paired[name][arm]["match"]
            gates[f"{arm}/{name}/covered"] = match["valid_cases"] >= spec["screen"]["coverage"] * len(panels[name])
            delta = match.get("match_delta")
            gates[f"{arm}/{name}/match"] = delta is not None and (delta > 0 if name == "all" else delta >= 0)
    for name, field in (("all_A", "OPB"), ("B_only", "UPB"), ("contains_C", "UPB"),
                        ("contains_C", "FM"), ("contains_C", "OPB"), ("all", "VG")):
        for arm in (plain, GENERIC, RP):
            score = paired[name][arm][field]
            gates[f"{arm}/{name}/{field}"] = (score["n"] >= spec["screen"]["coverage"] * len(panels[name])
                                                   and score["delta"] <= spec["screen"]["severity_margin"])
    ci = paired["all"][plain]["match"].get("95pct_source_bootstrap")
    gates["same_response_positive_interval"] = bool(ci and ci[0] > 0)
    return {"pass": all(gates.values()), "gates": gates, "paired": paired,
            "common": {k: score_matrix(sample, (*method.ARMS, *CONTROLS)) for k, sample in panels.items()},
            "changed": [r["uid"] for r in active_changes], "withheld": withheld,
            "contract_status": Counter(c["status"] for c in contracts.values()),
            "actor_status": Counter(r["actor"]["status"] for r in rows),
            "ledger": {stage: usage([r for r in ledger if r["unit"]["stage"] == stage]) for stage in spec["caps"]}}


def check(inputs):
    spec, jobs, roots, history, _, _ = inputs
    for uid, _, wire in jobs:
        payload = json.loads(wire["messages"][1]["content"])
        keys = {"task", "source_evidence", "task_choices", "witnesses"}
        if payload.keys() != keys or payload["task"] != roots[uid]["public_task"]:
            raise ValueError("Unexpected compiler input")
        uses, rejected = method.compile_uses(roots[uid], history[uid]["contract"], '{"uses":[]}')
        answers, trace = method.compile_answer("@ITEM 1\n" + history[uid]["draft"], history[uid]["contract"], uses,
                                               roots[uid]["public_task"]["query"])
        if len(set(answers.values())) != 1 or rejected or trace["uncovered_guard_slots"]:
            raise ValueError("A no-change render must be identical")
    print(json.dumps({"physical_requests": 0, "histories": len(jobs), "caps": spec["caps"]}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "verify"))
    action = parser.parse_args().action
    inputs = prepare()
    if action in ("check", "freeze"):
        check(inputs)
        if action == "freeze":
            probe.freeze(OUT / "FROZEN.json", inputs[0])
    else:
        probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT
        state = OUT / "RUN_STATE.json"
        with (probe.runner_lock(RUN / "runner.lock"), patch.object(parent.previous, "OUT", OUT),
              patch.object(parent.previous, "evaluate", evaluate), patch.object(parent.previous, "summarize", summarize)):
            done = state.exists() and read(state)["state"] == "COMPLETE"
            if action == "run" and not done:
                parent.previous.execute(inputs, live=True)
            elif action == "verify":
                if not done:
                    raise ValueError("Comparison has not settled")

                def same(path, value):
                    if read(path) != json.loads(json.dumps(value)):
                        raise ValueError(f"Replay changed {path.name}")

                with patch.object(probe, "freeze", same):
                    parent.previous.execute(inputs, live=False)
                print(json.dumps({"verified": True, "physical_requests": 0}))
