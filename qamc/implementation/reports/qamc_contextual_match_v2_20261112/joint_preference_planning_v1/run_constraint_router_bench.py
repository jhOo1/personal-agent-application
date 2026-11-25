"""Fill the exact BenchPreS task-only branch required by the archived hard-constraint router."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import run_effect_scope_transfer as runtime
import transfer_edit as transfer


BENCH = "BenchPreS"
ROUTER = "RP_IF_PREDICTED_HARD_CONSTRAINT"
OUT = runtime.OUT.with_name("guarded_answer_switch_rpeval_v1")
RUN = runtime.RUN.with_name("guarded_answer_switch_rpeval_v1")
probe, read = runtime.probe, runtime.read


def prepare(reference):
    panel = transfer.development_roots(BENCH)
    cases, protocol, controls = transfer.context(BENCH)
    archive = transfer.archived_answers(BENCH, cases)
    if {r["uid"] for r in panel} != cases.keys():
        raise ValueError("Frozen development input and scorer panels disagree")
    policy = {}
    for root in panel:
        uid = root["uid"]
        predictions = root["archived_policy"]
        if ([p["memory_id"] for p in predictions] != [s["memory_id"] for s in root["original_sources"]]
                or any(p["policy"] not in ("A", "B", "C") for p in predictions)):
            raise ValueError(f"Unexpected archived policy for {uid}")
        policy[uid] = transfer.RP if any(p["policy"] == "C" for p in predictions) else transfer.TASK_ONLY
    zero_roots = [r for r in panel if policy[r["uid"]] == transfer.TASK_ONLY]
    wires = transfer.draft_wires(zero_roots)
    known = {}
    needed = {sha(wire) for wire in wires.values()}
    for row in archive:
        if row["actor_status"] != "OK" or not row.get("actor_request"):
            continue
        digest = sha(row["actor_request"])
        if digest in needed:
            if digest in known and known[digest] != row["answer"]:
                raise ValueError("Conflicting archived task-only completions")
            known[digest] = row["answer"]
    raw_scores, conflicts = transfer.matching_grading_receipts(BENCH, cases, protocol, archive)
    code = [Path(__file__), Path(runtime.__file__), Path(transfer.__file__)]
    caps = {transfer.DRAFT: len(needed - known.keys()), **dict.fromkeys(transfer.bench.JUDGES, len(wires))}
    spec = {"panels": {BENCH: {"caps": caps, "policy": policy,
                              "draft_requests": {uid: sha(wire) for (uid, _, _), wire in wires.items()},
                              "preexisting_draft_count": len(known)}},
            "archive_sha256": sha([controls, raw_scores, conflicts, known]),
            "implementation_sha256": {path.name: sha(path.read_bytes()) for path in code},
            "service_reference_sha256": reference, "independent_confirmation": False}
    return spec, {BENCH: (policy, wires, known, cases, protocol, controls, raw_scores, conflicts)}


def evaluate(benchmark, inputs, dispatch):
    policy, wires, known, cases, protocol, controls, raw_scores, conflicts = inputs
    if benchmark != BENCH:
        raise ValueError("Unexpected benchmark")
    counts = Counter()
    drafts = transfer.cached_dispatch(dispatch, wires, known, (), counts)
    answers = [{"uid": uid, "method": arm, "actor_status": rec["status"], "answer": rec.get("answer"),
                "draft_request_sha256": rec["request_sha256"], "score": None}
               for (uid, arm, _), rec in drafts.items()]
    transfer.grade(BENCH, answers, cases, protocol,
                   lambda jobs: transfer.cached_dispatch(dispatch, jobs, raw_scores, conflicts, counts))
    scores = {(row["uid"], row["method"]): row["score"]
              for row in (*controls, *answers) if row["score"] is not None}
    for uid, choice in policy.items():
        if (uid, choice) in scores:
            scores[uid, ROUTER] = scores[uid, choice]
    compared = sorted({row["method"] for row in controls})
    no_c = {uid: cases[uid] for uid in cases if policy[uid] == transfer.TASK_ONLY}
    return {"assigned": len(cases), "routes": Counter(policy.values()),
            "routed_score_coverage": sum((uid, ROUTER) in scores for uid in cases),
            "rows": answers, "request_counts": counts,
            "paired": {arm: transfer.bench_pair(arm, ROUTER, cases, scores) for arm in compared},
            "no_constraint_paired": {arm: transfer.bench_pair(arm, ROUTER, no_c, scores) for arm in compared}}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    action = parser.parse_args().action
    with (
        probe.runner_lock(RUN / "bench_router.lock"),
        patch.object(runtime, "OUT", OUT),
        patch.object(runtime, "RUN", RUN),
        patch.object(runtime, "evaluate", evaluate),
    ):
        target = OUT / BENCH / "FROZEN.json"
        if action == "freeze":
            spec, _ = prepare(probe.read_reference()[1])
            probe.freeze(target, spec)
            print(json.dumps(spec["panels"][BENCH]["caps"]))
            return
        frozen = read(target)
        spec, payload = prepare(frozen["service_reference_sha256"])
        if spec != frozen:
            raise ValueError("Frozen BenchPreS comparison changed")
        if action == "verify":
            runtime.verify_replay(spec, payload, BENCH)
            return
        state = OUT / BENCH / "RUN_STATE.json"
        if state.exists() and read(state)["state"] == "COMPLETE":
            return
        if probe.read_reference()[1] != frozen["service_reference_sha256"]:
            raise ValueError("Service reference changed since freeze")
        runtime.execute(spec, payload, BENCH, live=True)


if __name__ == "__main__":
    main()
