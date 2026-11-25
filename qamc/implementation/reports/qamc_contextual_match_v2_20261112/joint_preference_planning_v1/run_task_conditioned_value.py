"""Run the matched task-contract comparison on the existing exposed RPEval roster."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import canonical, sha, token_estimate

import run_decision_transactions as parent
import task_conditioned_value as method
from settle_joint_planning import score_matrix, usage
from thinking_budget_transport import FIELD, MODEL, ThinkingBudgetSampler, validate_budget_request
from transaction_text_wire import ordinary_answer


OUT, RUN = parent.BASE_OUT.with_name("task_conditioned_value_rpeval_v1"), parent.BASE_RUN.with_name(
    "task_conditioned_value_rpeval_v1")
CONTRACT, ANSWER, JUDGE = "TaskContract", "ContractAnswer", parent.JUDGE
REFERENCE = "TASK_ONLY_CONTRACT"
probe, read, replay = parent.probe, parent.read, parent.replay
ARCHIVE = (*parent.method.MODES, *parent.ARCHIVED)
SOURCE = parent.previous.prior.old.prior.parent.prior.parent.joint


def prepare(panel):
    old_spec, _, roots, data, inherited = parent.prepare(panel)
    old_out = parent.BASE_OUT / panel
    if old_spec != read(old_out / "FROZEN.json") or read(old_out / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The corresponding archived comparison is not settled")
    settled = {row["uid"]: row for row in read(old_out / "SETTLED.json")["rows"]}
    roster, tasks = {}, {}
    for uid, previous in old_spec["roster"].items():
        task = roots[uid]["public_task"]
        digest = sha(task)
        tasks.setdefault(digest, task)
        roster[uid] = {"group": previous["group"], "task": digest,
                       "sources_sha256": sha(roots[uid]["original_sources"])}
    if len(tasks) != (5 if panel == "smoke" else 12):
        raise ValueError("The expected number of distinct public tasks changed")

    jobs = [(key, REFERENCE, method.contract_request(task)) for key, task in tasks.items()]
    files = (Path(__file__), Path(method.__file__), Path(__file__).with_name("TASK_CONDITIONED_VALUE_PROTOCOL.md"),
             old_out / "FROZEN.json", old_out / "SETTLED.json", old_out / f"{JUDGE}_EXACT.json")
    base = Path(__file__).resolve().parents[3]
    spec = {"panel": panel, "roster": roster, "task_hashes": {key: sha(w) for key, _, w in jobs},
            "input_sha256": {str(p.relative_to(base)): sha(p.read_bytes()) for p in files},
            "caps": {CONTRACT: len(tasks), ANSWER: 2 * len(roster), JUDGE: 2 * len(roster)},
            "service_reference_sha256": old_spec["service_reference_sha256"], "independent_confirmation": False,
            "coverage": .90, "severity_margin": .10}
    cache = {CONTRACT: {}, ANSWER: {}, JUDGE: {**inherited[JUDGE], **read(old_out / f"{JUDGE}_EXACT.json")}}
    return spec, jobs, roots, data, settled, cache


def evaluate(inputs, stage):
    spec, jobs, roots, data, settled, _ = inputs
    contracts, answers = {}, []
    for (key, _), (receipt, raw) in stage(CONTRACT, jobs).items():
        cell = contracts[key] = {"status": receipt["status"], "request_sha256": receipt["request_sha256"]}
        if cell["status"] == "OK":
            try:
                uid = next(uid for uid, row in spec["roster"].items() if row["task"] == key)
                cell["choices"] = method.contract(roots[uid]["public_task"], raw)
            except (TypeError, ValueError):
                cell["status"] = "INVALID_TASK_CONTRACT"
    rows = {}
    for uid, meta in spec["roster"].items():
        old = settled[uid]
        contract = contracts[meta["task"]]
        rows[uid] = row = {"uid": uid, **meta, "labels": data[uid]["labels"], "positions": data[uid]["positions"],
                           "outputs": {}, "attempts": {}, "native": dict(old["native"])}
        for arm in method.ARMS:
            row["native"][arm] = {"fields": {}, "status": contract["status"]}
            if contract["status"] == "OK":
                answers.append((uid, arm, method.answer_request(roots[uid], contract["choices"], arm)))

    reference = SOURCE.prior
    official = read(reference.formal.OUT / "PLAN.json")
    cases = reference.author_cases(official)
    scores = []
    for (uid, arm), (receipt, raw) in stage(ANSWER, answers).items():
        row = rows[uid]
        cell = row["attempts"][arm] = {"status": receipt["status"], "request_sha256": receipt["request_sha256"]}
        if cell["status"] == "OK":
            try:
                row["outputs"][arm] = ordinary_answer(raw)
            except ValueError:
                cell["status"] = "INVALID_ANSWER"
            else:
                scores.append((uid, arm, SOURCE.parent.grade_request(official, cases[uid], row["outputs"][arm])))
        row["native"][arm] = {"fields": {}, "status": cell["status"]}
    for (uid, arm), (receipt, raw) in stage(JUDGE, scores).items():
        row = rows[uid]
        row["native"][arm] = SOURCE.parent.parse_grade(receipt, raw, row["positions"])
    return contracts, list(rows.values())


def summarize(spec, contracts, rows, ledger):
    panels = {"all": rows, "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
              "B_only": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
              "contains_C": [r for r in rows if "C" in r["labels"]]}
    compare = SOURCE.parent.comparisons.grade_pair
    arms = (method.GENERIC, *ARCHIVE)
    paired = {name: {arm: {"match": replay.paired(cells, arm, method.CONDITIONAL),
                           **{f: compare(cells, arm, method.CONDITIONAL, f) for f in ("OPB", "UPB", "FM", "VG")}}
                     for arm in arms} for name, cells in panels.items()}
    gates = {}
    for panel in panels:
        for arm in (method.GENERIC, parent.method.ATOMIC, parent.method.ORDINARY, parent.ARCHIVED[-1]):
            stat = paired[panel][arm]["match"]
            gates[f"{panel}/{arm}/coverage"] = stat["valid_cases"] >= spec["coverage"] * len(panels[panel])
    for panel in ("all", "B_only", "contains_C"):
        for arm in (method.GENERIC, parent.method.ORDINARY, parent.ARCHIVED[-1]):
            value = paired[panel][arm]["match"].get("match_delta")
            gates[f"{panel}/{arm}/match"] = value is not None and (value > 0 if panel == "all" else value >= 0)
    for panel, field in (("all_A", "OPB"), ("B_only", "UPB"), ("contains_C", "UPB"), ("contains_C", "FM"), ("all", "VG")):
        stat = paired[panel][method.GENERIC][field]
        gates[f"{panel}/{field}"] = (stat["n"] >= spec["coverage"] * len(panels[panel]) and stat["n"] > 0
                                    and stat["delta"] <= spec["severity_margin"])
    improved = replay.paired(rows, method.GENERIC, method.CONDITIONAL).get("95pct_source_bootstrap")
    gates["generic_match_positive_interval"] = bool(improved and improved[0] > 0)
    return {"paired": paired, "common": {k: score_matrix(v, (*method.ARMS, *ARCHIVE)) for k, v in panels.items()},
            "gates": gates, "pass": spec["panel"] == "pilot" and all(gates.values()),
            "contract_status": Counter(c["status"] for c in contracts.values()),
            "generation_status": Counter(f"{arm}/{cell['status']}" for row in rows
                                         for arm, cell in row["attempts"].items()),
            "usage": {stage: usage([r for r in ledger if r["unit"]["stage"] == stage]) for stage in spec["caps"]}}


def manifest(panel, name, jobs):
    if name == JUDGE:
        return ORIGINAL_MANIFEST(panel, name, jobs)
    protocol = {"experiment": f"{OUT.name}/{panel}", "model": MODEL, "concurrency": 8,
                "spacing_seconds": 3.2, "automatic_retries": 0,
                "stages": {name: {"max_tokens": 8192, "temperature": 0, FIELD: method.BUDGET}}}
    units = []
    for uid, arm, wire in jobs:
        validate_budget_request(wire)
        if (wire["max_tokens"], wire["temperature"], wire[FIELD]) != (8192, 0, method.BUDGET):
            raise ValueError("Generation parameters differ from freeze")
        units.append({"unit": {"stage": name, "root_id": uid, "method": arm, "replicate": 0,
                               "protocol_sha256": sha(protocol)}, "request": wire})
    return {"protocol": protocol, "units": units}


ORIGINAL_MANIFEST = replay.manifest


def execute(inputs, *, live):
    spec, _, _, _, _, cache = inputs
    if spec != read(probe.OUT / "FROZEN.json"):
        raise ValueError("Inputs differ from frozen comparison")
    if live and probe.read_reference()[1] != spec["service_reference_sha256"]:
        raise ValueError("Gateway fingerprint changed")

    def stage(name, jobs):
        unique = {sha(w) for _, _, w in jobs} - cache[name].keys()
        if len(unique) > spec["caps"][name] or any(token_estimate(canonical(w["messages"])) > 32768 for _, _, w in jobs):
            raise ValueError("Frozen stage limit exceeded")
        sampler = probe.UsageObservableSampler if name == JUDGE else ThinkingBudgetSampler
        with patch.object(replay, "manifest", manifest), patch.object(probe, "UsageObservableSampler", sampler):
            results = replay.execute_stage(spec, spec["panel"], name, jobs, cache[name], live)
        for uid, arm, wire in jobs:
            record, _ = results[uid, arm]
            if record["request_sha256"] != sha(wire) or record["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise ValueError("Mismatched or unresolved receipt")
        return results

    out = probe.OUT
    if live:
        probe.atomic_json(out / "RUN_STATE.json", {"state": "RUNNING", "caps": spec["caps"]})
    try:
        contracts, rows = evaluate(inputs, stage)
        ledger = [record for name in spec["caps"] for record, _ in probe.stage_receipts(name).values()]
        probe.freeze(out / "SETTLED.json", {"contracts": contracts, "rows": rows, "ledger": ledger})
        probe.freeze(out / "RESULTS.json", summarize(spec, contracts, rows, ledger))
    except (ValueError, RuntimeError, OSError) as error:
        if live:
            probe.atomic_json(out / "RUN_STATE.json", {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(out / "RUN_STATE.json", {"state": "COMPLETE", "physical_requests": len(ledger)})


def check(inputs):
    spec, contracts, roots, _, _, _ = inputs
    for key, _, wire in contracts:
        payload = json.loads(wire["messages"][1]["content"])
        if set(payload) != {"task"} or sha(payload["task"]) != key:
            raise ValueError("Task contract input must be history-blind")
    for uid in spec["roster"]:
        left, right = (method.answer_request(roots[uid], [], arm) for arm in method.ARMS)
        if {**right, "messages": left["messages"]} != left or left["messages"][1] != right["messages"][1]:
            raise ValueError("Actor payload and sampling must match")

    def simulated(name, jobs):
        manifest(spec["panel"], name, jobs)
        result = {}
        for uid, arm, wire in jobs:
            if name == CONTRACT:
                query = json.loads(wire["messages"][1]["content"])["task"]["query"]
                raw = json.dumps({"decisions": [{"choice": "fixture", "task_quote": query[:20], "conditions": []}]})
            else:
                raw = "Offline fixture" if name == ANSWER else None
            result[uid, arm] = ({"status": "OK" if raw else "OFFLINE", "request_sha256": sha(wire)}, raw)
        return result

    contracts, rows = evaluate(inputs, simulated)
    assert len(contracts) == spec["caps"][CONTRACT] and all(len(row["outputs"]) == len(method.ARMS) for row in rows)
    assert not summarize(spec, contracts, rows, [])["pass"]
    print(json.dumps({"histories": len(rows), "caps": spec["caps"], "physical_requests": 0}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("panel", choices=("smoke", "pilot"))
    parser.add_argument("action", choices=("check", "freeze", "run", "verify"))
    args = parser.parse_args()
    inputs = prepare(args.panel)
    if args.action in ("check", "freeze"):
        check(inputs)
        if args.action == "freeze":
            probe.freeze(OUT / args.panel / "FROZEN.json", inputs[0])
    else:
        probe.OUT, probe.RUN, replay.OUT = OUT / args.panel, RUN / args.panel, OUT
        state = probe.OUT / "RUN_STATE.json"
        with probe.runner_lock(parent.BASE_RUN / "pilot" / "runner.lock"), probe.runner_lock(probe.RUN / "runner.lock"):
            done = state.exists() and read(state)["state"] == "COMPLETE"
            if args.action == "verify":
                if not done:
                    raise ValueError("Run is not settled")

                def compare(path, value):
                    if read(path) != json.loads(json.dumps(value)):
                        raise ValueError(f"Stored replay differs at {path.name}")

                with patch.object(probe, "freeze", compare):
                    execute(inputs, live=False)
                print(json.dumps({"state": "VERIFIED", "physical_requests": 0}))
            elif not done:
                if args.panel == "pilot":
                    smoke = OUT / "smoke"
                    statuses = read(smoke / "RESULTS.json")
                    if (read(smoke / "RUN_STATE.json")["state"] != "COMPLETE"
                            or statuses["contract_status"] != {"OK": 5}
                            or statuses["generation_status"] != {arm + "/OK": 5 for arm in method.ARMS}):
                        raise ValueError("Smoke must settle with all task contracts and answers usable")
                execute(inputs, live=True)
