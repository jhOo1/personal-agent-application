"""Acquire three direct ADD traces on the audited Strong Gate omission."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

import baselines
from census import normalized
from exposure_wires import rendered_projection
from residual_memory_delta import Delta, Entry, apply
from pilot_panel import source
from qamc.common import sha
from run_car import check_wire, engine, grading, probe
from trace_misuse import jobs, run as repeat
from trace_nonbold import response

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name("residual_bench_add_v1")
BENCH = "BenchPreS"
ACTORS = [f"AddDraw{i}" for i in repeat.REPEATS]
CAPS = {**dict.fromkeys(ACTORS, 1), "BenchAttrs": 30}


def prepare():
    candidates = [x for x in probe.read(HERE.parent / "strong_actor_boundary_audit_v1/CENSUS.json")["BenchPreS"]["attributes"]
                  if x["expression"] == "NO_EXACT_EXPRESSION" and x["base_follow"] != "follow"]
    audit, = candidates
    uid, position = audit["uid"], audit["position"]
    archive = baselines.archive
    cases, _, _ = archive.transfer.context(BENCH)
    card = baselines.transfer(BENCH)[uid]
    case = cases[uid]
    if case.get("independent_confirmation") or case.get("role", "DEV") != "DEV":
        raise ValueError("Need exposed development data")
    stored, = [r for r in archive.transfer.archived_answers(BENCH, {uid: case})
               if r["uid"] == uid and r["method"] == archive.engine.GATE and r["actor_status"] == "OK"]
    sources = card["root"]["original_sources"]
    order = tuple(r["memory_id"] for r in sources)
    visible = {r["memory_id"] for r in stored["view"]["source_evidence"]}
    existing = tuple(Entry(s) for s in order if s in visible)
    target, = [r["memory_id"] for r in sources if r["memory_id"] not in visible
               and normalized(audit["preference"]) in normalized(r["text"])]
    delta = Delta("ADD", target)
    updated = apply(order, existing, delta)
    before = [order.index(x.source) for x in existing]
    after = [order.index(x.source) for x in updated]
    old = stored["actor_request"]
    if (sha(old) != stored["actor_request_sha256"] or sha(old) != audit["actor_request_sha256"]
            or sha(stored["answer"]) != audit["answer_sha256"]):
        raise ValueError("Target audit and Strong Gate archive differ")

    plan = repeat.read(repeat.RUN / "PLAN_PRIVATE.json")
    repeated_case, = [r for r in plan["cases"] if r["uid"] == uid]
    if repeated_case["independent_confirmation"]:
        raise ValueError("Unexpected sealed comparison task")
    wave, = [i for i, batch in enumerate(plan["waves"]) if uid in batch]
    area = repeat.RUN / f"wave-{wave}"
    actor_jobs = jobs(area, "ACTOR")
    before_wire = {**old, "temperature": 1.0}
    rows = repeat.read(area / "RESULTS.json")
    control = []
    for i in repeat.REPEATS:
        archived = actor_jobs[uid, repeat.GATE, i, "Actor"]
        if archived["request"] != before_wire:
            raise ValueError("Repeated draw did not use the same Strong Gate Actor")
        answer = response(area, "generation", archived)
        row, = [r for r in rows if (r["uid"], r["method"], r["replicate"]) == (uid, repeat.GATE, i)]
        if not row["score"]:
            raise ValueError("Repeated Strong Gate grade unavailable")
        control.append({"draw": i, "score": row["score"], "answer_sha256": sha(answer)})

    bridge = source.PersistAuthorBridge(source.previous.parent.AUTHOR)
    template = bridge.blobs["GEPA"].decode()
    wire = rendered_projection(before_wire, [r["text"] for r in sources], after,
                               lambda history: bridge.render(history, before_wire["model"], template),
                               archived_positions=before, bench_guidance={})

    def task_and_guidance(request, positions):
        task = json.loads(request["messages"][1]["content"])
        guide = task.pop("selected_memory_use_guidance", [])
        return task, [(positions[item["memory_position_1_based"] - 1], item["use_instruction"])
                      for item in guide]

    if task_and_guidance(wire, after) != task_and_guidance(before_wire, before):
        raise ValueError("Evidence addition changed the task or retargeted usage instructions")
    check_wire(wire)
    frozen = {"benchmark": BENCH, "purpose": "label-directed development diagnostic",
              "original_wire_sha256": sha(before_wire), "add_wire_sha256": sha(wire),
              "case_sha256": sha(card["root"]), "baseline_draws_sha256": sha(control),
              "source_delta_sha256": sha(asdict(delta)), "target_position": position,
              "recorded_baseline_draws": len(control), "caps": CAPS,
              "code_sha256": sha({p: (HERE / p).read_text() for p in
                                  ("residual_memory_delta.py", "run_bench_add.py", "BENCH_ADD.md")})}
    return frozen, uid, position, wire, card, control


def execute(frozen, uid, position, wire, card, control, live):
    engine.OUT = probe.RUN = probe.OUT = RUN
    engine.CAP = CAPS
    identity = {"experiment_sha256": sha(frozen), "service_reference_sha256": probe.read_reference()[1]}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        if live:
            probe.freeze(RUN / "EXECUTION.json", identity)
        elif probe.read(RUN / "EXECUTION.json") != identity:
            raise ValueError("Execution environment drift")

        def stage(name, tasks, cache=None):
            return engine.stage(name, tasks, identity, live, ledger, cache)

        outputs = []
        for i, name in enumerate(ACTORS):
            record = stage(name, {(uid, "ADD"): wire})[uid, "ADD"]
            outputs.append({"uid": uid, "actor": record, "benchmark": BENCH, "method": f"ADD{i}",
                            "draw": i, "score": None, "group": card["group"], "stratum": card["stratum"],
                            "actor_status": record["status"], "answer": record["answer"]})
        grading(outputs, stage)
        out = {"control": control, "target_position": position, "outputs": outputs, "ledger": ledger}
        if live:
            probe.freeze(RUN / "RESULTS.json", out)
        elif probe.read(RUN / "RESULTS.json") != out:
            raise ValueError("Stored ADD receipts failed replay")
        scores = [r["score"] for r in outputs]
        metrics = ["aar_numerator", "aar_denominator", "mr_numerator", "mr_denominator", "task_completeness"]
        print({"baseline": [[r["score"]["decisions"][position]["label"], [r["score"][m] for m in metrics]]
                             for r in control],
               "add": [[s["decisions"][position]["label"], [s[m] for m in metrics]] if s else None
                       for s in scores],
               "statuses": dict(Counter(r["status"] for r in ledger)),
               "reported_tokens": sum((r.get("usage") or {}).get("total_tokens") or 0 for r in ledger),
               "unknown_usage": sum((r.get("usage") or {}).get("total_tokens") is None for r in ledger)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "replay"))
    args = parser.parse_args()
    frozen, *data = prepare()
    if args.action == "freeze":
        RUN.mkdir(mode=0o700, parents=True, exist_ok=True)
        probe.freeze(RUN / "FROZEN.json", frozen)
        print(frozen)
    elif frozen != probe.read(RUN / "FROZEN.json"):
        raise ValueError("Frozen intervention drift")
    else:
        execute(frozen, *data, live=args.action == "run")
