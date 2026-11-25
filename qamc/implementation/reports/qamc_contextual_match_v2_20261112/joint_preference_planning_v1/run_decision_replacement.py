"""Evaluate the identical-proposal model-pick and program-pick policies."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import decision_replacement as method
import run_task_conditioned_value as previous
from settle_joint_planning import score_matrix, usage
from transaction_text_wire import packet_marker


OUT = previous.OUT.with_name("decision_replacement_rpeval_v1")
RUN = previous.RUN.with_name(OUT.name)
PROPOSAL, JUDGE = "DecisionReplacement", previous.JUDGE
probe, read, replay = previous.probe, previous.read, previous.replay
REFERENCE = previous.SOURCE.prior
SCORER = previous.SOURCE.parent
GENERIC = previous.method.GENERIC
ATOMIC, GATE, RP = previous.parent.method.ATOMIC, *previous.parent.ARCHIVED[-2:]
CONTROLS = (GENERIC, ATOMIC, GATE, RP)


def prepare():
    original, _, roots, data, _, inherited = previous.prepare("pilot")
    recovered = previous.OUT / "contract_recovery"
    if read(recovered / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("Previous task contracts must be settled")
    archive = read(recovered / "SETTLED.json")
    old, jobs, history = {}, [], {}
    for row in archive["rows"]:
        uid, task = row["uid"], row["task"]
        history[uid] = {"contract": archive["contracts"][task]["choices"],
                        "draft": data[uid]["blocks"]["D1"]["lines"][0]}
        old[uid] = {k: row[k] for k in ("uid", "group", "task", "positions", "labels")} | {
            "native": {arm: row["native"][arm] for arm in CONTROLS}}
        jobs.append((uid, "SHARED", method.make_request(roots[uid], **history[uid])))
    cache = {PROPOSAL: {}, JUDGE: {**inherited[JUDGE]}}
    for folder in ("pilot", "contract_recovery"):
        cache[JUDGE].update(read(previous.OUT / folder / f"{JUDGE}_EXACT.json"))
    official = read(REFERENCE.formal.OUT / "PLAN.json")
    cases = REFERENCE.author_cases(official)
    if len(jobs) != 55 or not old.keys() <= cases.keys():
        raise ValueError("Unexpected exposed case roster")
    spec = {"panel": "pilot", "cases": {uid: sha(w) for uid, _, w in jobs},
            "caps": {PROPOSAL: len(jobs), JUDGE: 2 * len(jobs)},
            "service_reference_sha256": original["service_reference_sha256"],
            "parent_sha256": sha(archive), "judge_cache_sha256": sha(cache[JUDGE]),
            "method_sha256": sha(Path(method.__file__).read_bytes()), "runner_sha256": sha(Path(__file__).read_bytes()),
            "protocol_sha256": sha(Path(__file__).with_name("DECISION_REPLACEMENT_PROTOCOL.md").read_bytes()),
            "score_guard": {"common": .90, "severity_guard": .10, "min_changed_groups": 2},
            "independent_confirmation": False, "automatic_retries": 0}
    return spec, jobs, roots, history, (old, official, cases), cache


def evaluate(inputs, stage):
    _, jobs, roots, history, (rows, official, cases), _ = inputs
    responses, grade_jobs = stage(PROPOSAL, jobs), []
    for uid, shared, wire in jobs:
        row = rows[uid]
        rec, raw = responses[uid, shared]
        row["generation"] = {"status": rec["status"], "request_sha256": rec["request_sha256"]}
        row["outputs"], row["picks"], row["rejected"] = {}, {}, []
        if rec["status"] == "OK":
            try:
                row["outputs"], row["picks"], row["rejected"] = method.compile_answers(
                    raw, wire, roots[uid], **history[uid])
            except (KeyError, TypeError, ValueError, AttributeError):
                row["generation"]["status"] = "INVALID_PROPOSAL"
        for arm in method.ARMS:
            row["native"][arm] = {"fields": {}, "status": row["generation"]["status"]}
            if arm in row["outputs"]:
                grade_jobs.append((uid, arm, SCORER.grade_request(official, cases[uid], row["outputs"][arm])))
    for (uid, arm), (receipt, raw) in stage(JUDGE, grade_jobs).items():
        rows[uid]["native"][arm] = SCORER.parse_grade(receipt, raw, rows[uid]["positions"])
    return {}, list(rows.values())


def summarize(spec, _, rows, ledger):
    left, right = method.ARMS
    panels = {"all": rows, "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
              "B_only": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
              "contains_C": [r for r in rows if "C" in r["labels"]]}
    paired = {name: {arm: {"match": replay.paired(sample, arm, right),
                           **{f: SCORER.comparisons.grade_pair(sample, arm, right, f) for f in ("OPB", "UPB", "FM", "VG")}}
                     for arm in (left, *CONTROLS)} for name, sample in panels.items()}
    changed = [r for r in rows if r["outputs"].get(left) != r["outputs"].get(right)]
    groups = sorted({r["group"] for r in changed})
    metrics = spec["score_guard"]
    checks = {"different_groups": len(groups) >= metrics["min_changed_groups"]}
    for arm in (left, GENERIC, RP, GATE):
        for panel, sample in panels.items():
            match = paired[panel][arm]["match"]
            value = match.get("match_delta")
            checks[f"{arm}/{panel}/coverage"] = match["valid_cases"] >= metrics["common"] * len(sample)
            checks[f"{arm}/{panel}/match"] = value is not None and (value > 0 if panel == "all" else value >= 0)
    for panel, f in (("all_A", "OPB"), ("B_only", "UPB"), ("contains_C", "OPB"),
                     ("contains_C", "UPB"), ("contains_C", "FM"), ("all", "VG")):
        for arm in (left, GENERIC):
            cell = paired[panel][arm][f]
            checks[f"{arm}/{panel}/{f}"] = (cell["n"] >= metrics["common"] * len(panels[panel])
                                               and cell["delta"] <= metrics["severity_guard"])
    ci = paired["all"][left]["match"].get("95pct_source_bootstrap")
    checks["shared_proposal_interval"] = bool(ci and ci[0] > 0)
    return {"pass": all(checks.values()), "checks": checks, "changed_cases": [r["uid"] for r in changed],
            "changed_groups": groups, "paired": paired,
            "common": {k: score_matrix(sample, (*method.ARMS, *CONTROLS)) for k, sample in panels.items()},
            "generation_status": Counter(r["generation"]["status"] for r in rows),
            "usage": {stage: usage([r for r in ledger if r["unit"]["stage"] == stage]) for stage in spec["caps"]}}


def check(inputs):
    spec, jobs, roots, history, _, _ = inputs
    for uid, _, wire in jobs:
        record = history[uid]
        marker = packet_marker(wire["messages"][1]["content"])
        outputs, picks, errors = method.compile_answers('{"units":[]}\n' + marker + " END",
                                                        wire, roots[uid], **record)
        if any(v != record["draft"] for v in outputs.values()) or any(picks.values()) or errors:
            raise ValueError("A no-change response must reproduce the exact source draft")
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
        with (probe.runner_lock(RUN / "runner.lock"), patch.object(previous, "OUT", OUT),
              patch.object(previous, "evaluate", evaluate), patch.object(previous, "summarize", summarize)):
            done = state.exists() and read(state)["state"] == "COMPLETE"
            if action == "run" and not done:
                previous.execute(inputs, live=True)
            elif action == "verify":
                if not done:
                    raise ValueError("Comparison has not settled")

                def same(path, value):
                    if read(path) != json.loads(json.dumps(value)):
                        raise ValueError(f"Replay changed {path.name}")

                with patch.object(probe, "freeze", same):
                    previous.execute(inputs, live=False)
                print(json.dumps({"verified": True, "physical_requests": 0}))
