"""Compare the new rank fusion to original RP using the same Actor on exposed RPEval."""
from argparse import ArgumentParser
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import audit_asymmetric_preference_fusion as fusion
import run_active_source_ids as active
from settle_joint_planning import score_matrix
from transaction_text_wire import ordinary_answer


OUT = active.OUT.with_name("asymmetric_preference_fusion_rpeval_v1")
RUN = active.RUN.with_name(OUT.name)
BASE, METHOD = "ORIGINAL_FUSION", "CONTEXT_FIRST_FUSION"
ARCHIVED = active.outcome.RP
ACTOR, JUDGE = "FusionActor", active.JUDGE
probe, read, replay = active.probe, active.read, active.replay
runner, scorer = active.runner, active.scorer


def prepare(reference):
    prior = replay.prior
    plan = read(prior.OUT / "FROZEN.json")
    roster = {root["uid"] for root in read(prior.NARROW)["roots"]}
    roots = {root["uid"]: root for root in plan["roots"] if root["uid"] in roster}
    original = read(prior.formal.OUT / "PLAN.json")
    cases = prior.author_cases(original)
    _, labels, archived = fusion.native_controls(prior.formal.OUT)
    estimates = {item["uid"]: item for item in fusion.audit()["cells"] if item["uid"] in roots}
    if len(roster) != 118 or roots.keys() != roster or not roster <= (cases.keys() & estimates.keys()):
        raise ValueError("The exposed 118-case allocation changed")
    jobs, rows, cache, changes = [], {}, {ACTOR: {}, JUDGE: {}}, []
    for uid, root in roots.items():
        old_wire = root["archived_actor_request"]
        if sha(old_wire) != sha(archived[uid]["actor_request"]):
            raise ValueError("Original RP Actor differs from the selected public snapshot")
        old_view = json.loads(old_wire["messages"][1]["content"])
        new_policy = estimates[uid]["policy"]
        row = rows[uid] = {
            "uid": uid, "group": root["group"], "labels": list(labels[uid]["author_labels"]),
            "positions": len(root["original_sources"]),
            "old_policy": root["archived_policy"], "new_policy": new_policy, "outputs": {}, "actor": {},
            "native": {arm: root["archived"][arm] for arm in (ARCHIVED, active.outcome.GATE)},
        }
        if len(row["labels"]) != row["positions"]:
            raise ValueError("The evaluator and public source count disagree")
        for arm, datum in row["native"].items():
            native_raw = datum["raw_judge"]
            if native_raw is None:
                continue
            score_wire = scorer.grade_request(original, cases[uid], datum["answer"])
            digest = sha(score_wire)
            receipt = prior.receipt(original, uid, arm, JUDGE)
            if (not receipt or receipt["request_sha256"] != digest
                    or receipt["response"]["answer"] != native_raw):
                raise ValueError("The archived judge answer does not match the frozen wire")
            if digest in cache[JUDGE] and cache[JUDGE][digest][1] != native_raw:
                raise ValueError("Conflicting exact grade receipts")
            cache[JUDGE][digest] = [receipt, native_raw]
        if new_policy == old_view["preference_use_policy"]:
            row["outputs"] = dict.fromkeys((BASE, METHOD), row["native"][ARCHIVED]["answer"])
            for arm in (BASE, METHOD):
                row["native"][arm] = {**row["native"][ARCHIVED], "reuse": ARCHIVED}
                row["actor"][arm] = {"status": "IDENTICAL_ARCHIVED_WIRE", "request_sha256": sha(old_wire)}
            continue
        changed = deepcopy(old_wire)
        changed["messages"][1]["content"] = json.dumps({**old_view, "preference_use_policy": new_policy},
                                                        ensure_ascii=False)
        if [x["memory_id"] for x in new_policy] != [x["memory_id"] for x in root["original_sources"]]:
            raise ValueError("The proposed policy misaligned source identities")
        jobs.extend(((uid, BASE, old_wire), (uid, METHOD, changed)))
        changes.append(uid)
    if len(changes) != 39:
        raise ValueError("Unexpected number of policy changes in the frozen panel")
    paths = (Path(__file__), Path(fusion.__file__), Path(__file__).with_name("ASYMMETRIC_FUSION_PROTOCOL.md"))
    spec = {"panel": "matched", "caps": {ACTOR: len(jobs), JUDGE: len(jobs)},
            "service_reference_sha256": reference,
            "original_service_reference_matches": reference == original["service_reference_sha256"],
            "requests": {uid: {name: sha(wire) for case, name, wire in jobs if case == uid} for uid in changes},
            "rows_sha256": sha(rows), "judge_cache_sha256": sha(cache[JUDGE]),
            "code_sha256": {path.name: sha(path.read_bytes()) for path in paths},
            "thresholds": {"coverage": .90, "match_noninferiority_pp": .02, "average_severity_margin": .05}}
    return spec, jobs, changes, roots, (rows, original, cases), cache


def evaluate(inputs, stage):
    _, jobs, _, _, (rows, original, cases), _ = inputs
    responses = stage(ACTOR, jobs)
    scores = []
    for uid, arm, wire in jobs:
        record, raw = responses[uid, arm]
        state = record["status"]
        if state == "OK":
            try:
                answer = ordinary_answer(raw)
            except ValueError:
                state = "INVALID_ACTOR_TEXT"
            else:
                rows[uid]["outputs"][arm] = answer
                scores.append((uid, arm, scorer.grade_request(original, cases[uid], answer)))
        rows[uid]["actor"][arm] = {"status": state, "request_sha256": sha(wire)}
        rows[uid]["native"][arm] = {"fields": {}, "status": state}
    for (uid, arm), (record, raw) in stage(JUDGE, scores).items():
        rows[uid]["native"][arm] = scorer.parse_grade(record, raw, rows[uid]["positions"])
    return {}, list(rows.values())


def compare(rows, left):
    match = replay.paired(rows, left, METHOD)
    shared = set(match["valid_uids"])
    valid = [row for row in rows if row["uid"] in shared]
    return {"match": match, **{field: scorer.comparisons.grade_pair(valid, left, METHOD, field)
                               for field in active.METRICS}}


def summarize(spec, _, rows, ledger):
    cohorts = {"assigned": rows,
               "changed": [row for row in rows if row["uid"] in spec["requests"]],
               "all_A": [row for row in rows if set(row["labels"]) == {"A"}],
               "B_only": [row for row in rows if "B" in row["labels"] and "C" not in row["labels"]],
               "has_C": [row for row in rows if "C" in row["labels"]]}
    comps = {name: {arm: compare(sample, arm) for arm in (BASE, ARCHIVED, active.outcome.GATE)}
             for name, sample in cohorts.items()}
    limits = spec["thresholds"]
    gates = {}
    for name in ("assigned", "changed", "all_A", "B_only", "has_C"):
        match = comps[name][BASE]["match"]
        gates[name + "/coverage"] = match["valid_cases"] >= limits["coverage"] * len(cohorts[name])
    gates["main_positive_cluster_interval"] = comps["assigned"][BASE]["match"].get(
        "95pct_source_bootstrap", [-1])[0] > 0
    gates["lower_all_A_OPB"] = comps["all_A"][BASE]["OPB"].get("delta", 1) < 0
    gates["overall_full_match"] = comps["assigned"][BASE]["full_match"].get("delta", -1) >= 0
    for name in ("B_only", "has_C"):
        summary = comps[name][BASE]
        gates[name + "/match_protected"] = summary["match"].get("95pct_source_bootstrap", [-1])[0] >= (
            -limits["match_noninferiority_pp"])
        for field in ("UPB", "FM"):
            entry = summary[field]
            gates[name + "/" + field] = (entry["n"] >= limits["coverage"] * len(cohorts[name])
                                         and entry.get("95pct_source_bootstrap", [0, 1])[1]
                                         <= limits["average_severity_margin"])
    return {"gates": gates, "passed": all(gates.values()), "comparisons": comps,
            "common": {name: score_matrix(sample, (BASE, METHOD, ARCHIVED, active.outcome.GATE))
                       for name, sample in cohorts.items()},
            "ledger": {stage: active.usage([record for record in ledger if record["unit"]["stage"] == stage])
                       for stage in spec["caps"]}}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    action = parser.parse_args().action
    frozen = OUT / "FROZEN.json"
    reference = probe.read_reference()[1] if action == "freeze" else read(frozen)["service_reference_sha256"]
    inputs = prepare(reference)
    if action == "freeze":
        # Inspect the actual stage manifest before allowing model dispatch.
        with patch.object(replay, "ACTOR", ACTOR):
            runner.ORIGINAL_MANIFEST(inputs[0]["panel"], ACTOR, inputs[1])
        probe.freeze(frozen, inputs[0])
        print(json.dumps(inputs[0]["caps"]))
        return
    if read(frozen) != inputs[0]:
        raise ValueError("The frozen experiment changed")
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT
    with (
        probe.runner_lock(RUN / "runner.lock"),
        patch.object(runner, "evaluate", evaluate),
        patch.object(runner, "summarize", summarize),
        patch.object(replay, "ACTOR", ACTOR),
        patch.object(runner, "manifest", runner.ORIGINAL_MANIFEST),
        patch.object(runner, "ThinkingBudgetSampler", probe.UsageObservableSampler),
    ):
        state = OUT / "RUN_STATE.json"
        done = state.exists() and read(state)["state"] == "COMPLETE"
        if action == "run" and not done:
            runner.execute(inputs, live=True)
        if action == "verify":
            if not done:
                raise ValueError("Comparison has not settled")

            def exact(path, value):
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError(f"Replay mismatch in {path.name}")

            with patch.object(probe, "freeze", exact):
                runner.execute(inputs, live=False)
            print(json.dumps({"verified": True, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
