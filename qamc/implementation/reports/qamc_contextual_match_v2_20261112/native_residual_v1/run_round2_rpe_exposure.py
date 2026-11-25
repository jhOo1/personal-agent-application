"""Test per-source versus whole-history execution of shared archived predictions."""
import argparse
import json
from copy import deepcopy

from freeze_round2_rpe import panel
from incremental_panel import HERE, prior, read, sha
from run_probe import engine, probe

OUT = HERE / "round2_rpe_exposure_v1"
RUN = engine.RUN.with_name(OUT.name)
STAGE = "MixedHistoryActor"
METHODS = ("PER_SOURCE", "WHOLE_HISTORY")


def compile_wires(wire, expected_hash):
    if sha(wire) != expected_hash:
        raise ValueError("Archived request drift")
    user, = [m for m in wire["messages"] if m["role"] == "user"]
    packet = json.loads(user["content"])
    predictions = packet["preference_use_policy"]
    sources = packet["source_evidence"]
    ids = [source["memory_id"] for source in sources]
    if (len(ids) != len(set(ids)) or [p["memory_id"] for p in predictions] != ids
            or any(set(p) != {"memory_id", "policy"} or p["policy"] not in {"A", "B", "C"}
                   for p in predictions)):
        raise ValueError("Archived prediction contract differs from the frozen contract")
    keep = {p["memory_id"] for p in predictions if p["policy"] in {"B", "C"}}
    result = {}
    for method in METHODS:
        visible = sources if method == "WHOLE_HISTORY" and keep else [
            source for source in sources if source["memory_id"] in keep]
        derived = deepcopy(wire)
        derived_user, = [m for m in derived["messages"] if m["role"] == "user"]
        derived_user["content"] = json.dumps({**packet, "source_evidence": visible}, ensure_ascii=False)
        result[method] = derived
    return result


def prepare():
    roster = read(HERE / "ROUND2_RPE_MIXED_PANEL.json")
    if roster != panel():
        raise ValueError("Frozen panel drift")
    v41 = prior.R["archived"].v41
    frozen = read(v41.OUT / "FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Expected exposed development cohort")
    roots = {r["uid"]: r for r in frozen["roots"]}
    eligible = {row["uid"] for row in roster["rows"]}
    originals = {r["uid"]: r for r in read(v41.formal.OUT / "RESULT_ROWS.json")
                 if r["uid"] in eligible and r["method"] == "RPR_PAPER_FULL"}
    jobs = {}
    for row in roster["rows"]:
        uid = row["uid"]
        original = originals[uid]
        arms = compile_wires(original["actor_request"], original["actor_request_sha256"])
        jobs.update({(uid, method): wire for method, wire in arms.items()})
    return roster, {uid: roots[uid] for uid in eligible}, jobs


def main(live):
    roster, roots, jobs = prepare()
    caps = {STAGE: len(jobs), engine.RPE: len(jobs)}
    identity = {
        "service_reference_sha256": probe.read_reference()[1],
        "experiment_sha256": sha([roster, [[uid, method, sha(wire)]
                                            for (uid, method), wire in jobs.items()],
                                  caps, sha((HERE / "run_round2_rpe_exposure.py").read_bytes())]),
    }
    if not live:
        print(f"Verified {len(jobs)} matched requests across {len(roots)} groups")
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, caps
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, wires, cache=None):
            return engine.stage(stage, wires, identity, True, ledger, cache) if wires else {}

        rows = [
            {"uid": uid, "method": method, "actor_status": reply["status"],
             "answer": reply.get("answer"), "score": None}
            for (uid, method), reply in dispatch(STAGE, jobs).items()
        ]
        engine.grade_rpe(roots, rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "run"))
    main(parser.parse_args().action == "run")
