"""Run the same frozen fusion comparison on exposed BenchPreS and PersistBench."""
from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

from audit_asymmetric_fusion_transfer import audit
from audit_asymmetric_preference_fusion import fuse
import run_effect_scope_transfer as runtime
from settle_realization_transfer import bench_comparison, persist_comparison
import transfer_edit as transfer


OUT = runtime.OUT.with_name("asymmetric_preference_fusion_transfer_v1")
RUN = runtime.RUN.with_name(OUT.name)
ORIGINAL, METHOD = "ORIGINAL_FUSION", "CONTEXT_FIRST_FUSION"
ACTOR = "FusionTransferActor"
probe, read = runtime.probe, runtime.read


def prepare(name, reference):
    cases, protocol, controls = transfer.context(name)
    roots = {row["uid"]: row for row in transfer.development_roots(name)}
    frozen = {row["uid"]: row for row in audit(name)["rows"]}
    if roots.keys() != cases.keys() or roots.keys() != frozen.keys():
        raise ValueError("Transfer policy, public cases and scorers disagree")
    jobs = {}
    for uid, root in roots.items():
        archived = root["archived_actor_request"]
        result = frozen[uid]
        if sha(archived) != result["original_sha256"]:
            raise ValueError("Archived Actor input changed")
        if not result["changed"]:
            continue
        baseline = json.loads(archived["messages"][1]["content"])
        policy = [{"memory_id": source["memory_id"], "policy": degree}
                  for source, degree in zip(root["original_sources"], result["after"], strict=True)]
        if (baseline["preference_use_policy"] != root["archived_policy"]
                or baseline["source_evidence"] != root["original_sources"]
                or {key: baseline[key] for key in root["public_task"]} != root["public_task"]):
            raise ValueError("Transfer wire differs from the ordered public inputs")
        modified = deepcopy(archived)
        modified["messages"][1]["content"] = json.dumps({**baseline, "preference_use_policy": policy},
                                                         ensure_ascii=False)
        jobs[uid, ORIGINAL, ACTOR] = archived
        jobs[uid, METHOD, ACTOR] = modified
    if len({(w["model"], w["max_tokens"], w["temperature"]) for w in jobs.values()}) != 1:
        raise ValueError("Transfer Actor allocation mixed sampling settings")
    if len({sha(wire) for wire in jobs.values()}) != len(jobs):
        raise ValueError("Unexpected duplicate exact Actor wires")
    archive = transfer.archived_answers(name, cases)
    cached, conflicts = transfer.matching_grading_receipts(name, cases, protocol, archive)
    stages = transfer.bench.JUDGES if name == "BenchPreS" else (transfer.persist.STAGE,)
    spec = {
        "panels": {name: {"assigned": sorted(roots), "caps": {ACTOR: len(jobs), **dict.fromkeys(stages, len(jobs))},
                          "actor_requests": {uid + "/" + arm: sha(wire) for (uid, arm, _), wire in jobs.items()}}},
        "service_reference_sha256": reference, "independent_confirmation": False,
        "retained_archive_sha256": sha([controls, cached, conflicts]),
        "code_sha256": {path.name: sha(path.read_bytes()) for path in (
            Path(__file__), Path(fuse.__code__.co_filename), Path(runtime.__file__),
            Path(__file__).with_name("ASYMMETRIC_FUSION_TRANSFER_PROTOCOL.md"))},
    }
    return spec, {name: (cases, protocol, controls, frozen, jobs, cached, conflicts)}


def evaluate(name, inputs, dispatch):
    cases, protocol, controls, frozen, jobs, cached, conflicts = inputs
    physical = transfer.checked_dispatch(dispatch, jobs)
    counts = Counter()
    answers = [{"uid": uid, "method": arm, "actor_status": rec["status"], "answer": rec.get("answer"),
                "actor_request_hash": rec["request_sha256"], "score": None} for (uid, arm, _), rec in physical.items()]
    transfer.grade(name, answers, cases, protocol,
                   lambda grades: transfer.cached_dispatch(dispatch, grades, cached, conflicts, counts))
    cells = {(row["uid"], row["method"]): row["score"] for row in (*controls, *answers) if row["score"] is not None}
    for uid, result in frozen.items():
        if not result["changed"] and (uid, transfer.RP) in cells:
            for arm in (ORIGINAL, METHOD):
                cells[uid, arm] = cells[uid, transfer.RP]
    compare = bench_comparison if name == "BenchPreS" else persist_comparison
    participants = (ORIGINAL, *sorted({row["method"] for row in controls}))
    cohorts = {"assigned": cases, "changed": {uid: case for uid, case in cases.items() if frozen[uid]["changed"]}}
    return {
        "assigned": len(cases), "scorer": protocol["model"],
        "paired": {cohort: {arm: compare([(case, cells[uid, arm], cells[uid, METHOD])
                                         for uid, case in subset.items()
                                         if (uid, arm) in cells and (uid, METHOD) in cells])
                            for arm in participants} for cohort, subset in cohorts.items()},
        "rows": answers, "available": {arm: sum((uid, arm) in cells for uid in cases) for arm in (ORIGINAL, METHOD)},
        "retrieval_or_estimator_requests": 0, "score_reuse": counts,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    parser.add_argument("benchmark", choices=transfer.PANELS)
    options = parser.parse_args()
    action, benchmark = options.action, options.benchmark
    with (
        probe.runner_lock(RUN / "runner.lock"),
        patch.object(runtime, "OUT", OUT),
        patch.object(runtime, "RUN", RUN),
        patch.object(runtime, "evaluate", evaluate),
    ):
        frozen = OUT / benchmark / "FROZEN.json"
        reference = probe.read_reference()[1] if action == "freeze" else read(frozen)["service_reference_sha256"]
        spec, data = prepare(benchmark, reference)
        if action == "freeze":
            probe.freeze(frozen, spec)
            print(json.dumps(spec["panels"][benchmark]["caps"]))
        elif spec != read(frozen):
            raise ValueError("Transfer freeze inputs or implementation changed")
        elif action == "verify":
            runtime.verify_replay(spec, data, benchmark)
        else:
            state = OUT / benchmark / "RUN_STATE.json"
            if not state.exists() or read(state)["state"] != "COMPLETE":
                runtime.execute(spec, data, benchmark, live=True)


if __name__ == "__main__":
    main()
