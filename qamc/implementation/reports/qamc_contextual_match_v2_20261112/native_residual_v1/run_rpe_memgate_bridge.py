"""Score exposed MemGate release answers against the frozen RPEval rubric."""
import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from incremental_panel import HERE, prior, read, sha
from run_probe import engine, probe
from qamc.pa.core import digest, rpeval_public
import run_qamc_memgate_external as legacy

OUT = HERE / "rpe_memgate_bridge_v1"
RUN = engine.RUN.with_name(OUT.name)
PANEL = HERE / "RPE_MEMGATE_BRIDGE_PANEL.json"
METHOD = "MG_RELEASE"


def source_key(card):
    return card["source_file"].split("benchmark_dataset/")[-1], card["row_index"]


def prepare():
    v41 = prior.R["archived"].v41
    formal = v41.formal.OUT
    manifest = read(formal / "MANIFEST_300.json")
    native = {source_key(c): c for c in manifest}
    if len(native) != len(manifest):
        raise ValueError("Duplicate author identity")
    parent = read(formal / "PLAN.json")
    scorer_cases = engine.transport.author_cases(parent)
    routes = {r["uid"]: r for r in read(HERE.parent / "ipe_c_two_endpoint_completion_v1" / "RESULTS.json")["rows"]}
    release = read(legacy.OUT / "RESULTS.json")
    if release["independent_confirmation"] is not False:
        raise ValueError("Expected archived development cases")
    answers = {r["uid"]: r for r in release["rows"] if r["method"] == METHOD}
    actors = {(u["unit"]["root_id"], u["unit"]["method"]): u["request"]
              for u in read(legacy.OUT / "ACTOR_MANIFEST.json")["units"]}
    roster, rows, roots, jobs = [], [], {}, {}
    for old in read(legacy.OUT / "FROZEN_VIEWS.json"):
        card = old["case"]
        if card["benchmark"] != "rpeval" or not card["track"].endswith("/multi"):
            continue
        c = native[source_key(card)]
        uid, old_uid = c["uid"], old["uid"]
        ref = read(legacy.ROOT / c["evaluation_path"])
        if (card["independent_confirmation"] or c["independent_confirmation"]
                or c["evaluation_hash"] != card["evaluation_hash"]
                or read(legacy.ROOT / card["evaluation_path"]) != ref
                or sha(ref) != c["native_row_sha256"]):
            raise ValueError(f"Not the same exposed source: {uid}")
        before = rpeval_public(ref, old_uid, c["track"].startswith("implicit"))
        old_public = read(legacy.ROOT / card["public_path"])
        if (digest(old_public) != card["public_hash"]
                or json.loads(json.dumps(asdict(before))) != old_public):
            raise ValueError(f"Legacy public hash or adapter drift: {old_uid}")
        source = before.payload()
        view = old["views"][METHOD]
        source_by_id = {r["memory_id"]: r["text"] for r in source["memories"]}
        if (view["query"] != source["query"] or view["current_context"] != source["current_context"]
                or view["facts"] != source["fixed_facts"]
                or any(source_by_id.get(r["memory_id"]) != r["text"] for r in view["source_evidence"])):
            raise ValueError(f"Legacy Actor view drift: {uid}")
        row = answers[old_uid]
        shot = legacy.output(row["actor_unit"])
        wire = actors[old_uid, METHOD]
        if (shot is None or sha(wire) != shot["request_sha256"]
                or wire["model"] != "qwen3.8-flash"):
            raise ValueError(f"Original Actor receipt/wire mismatch: {uid}")
        answer = row.get("answer")
        if shot["status"] == "OK" and (not answer or shot["response"]["answer"] != answer):
            raise ValueError(f"Archived answer drift: {uid}")
        status = "OK" if answer and shot["status"] == "OK" else shot["status"]
        entry = {"uid": uid, "method": METHOD, "actor_status": status, "answer": answer, "score": None}
        judge_hash = None
        if status == "OK":
            jobs[uid, METHOD] = engine.rpe_wire(parent, scorer_cases[uid], entry)
            judge_hash = sha(jobs[uid, METHOD])
        roots[uid] = {"original_sources": source["memories"], "archived": {}}
        roster.append({"uid": uid, "legacy_uid": old_uid, "group": c["analysis_group_id"],
                       "author_row_sha256": c["native_row_sha256"], "actor_status": status,
                       "actor_request_sha256": sha(wire), "answer_sha256": sha(answer) if answer else None,
                       "judge_request_sha256": judge_hash})
        rows.append({**entry, "base_score": routes[uid]["ipe_c"]["grade"],
                     "labels": ref["intent_type"]})
    if len(roster) != 24 or len(roots) != len(roster):
        raise ValueError("Unexpected exposed multi-roster overlap")
    return roster, rows, roots, jobs


def main(action):
    roster, rows, roots, jobs = prepare()
    if action == "freeze":
        probe.freeze(PANEL, roster)
    if roster != read(PANEL):
        raise ValueError("Frozen bridge drift")
    if action != "run":
        print({"allocated": len(rows), "Actor_status": dict(Counter(r["actor_status"] for r in rows)),
               "max_grading_requests": len(jobs), "new_actors": 0})
        return
    engine.OUT = probe.OUT = OUT
    probe.RUN, engine.CAP = RUN, {engine.RPE: len(jobs)}
    identity = {"service_reference_sha256": probe.read_reference()[1],
                "experiment_sha256": sha([roster, sha(Path(__file__).read_bytes())])}
    OUT.mkdir(exist_ok=True)
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(OUT / "EXECUTION.json", identity)

        def dispatch(stage, wires, cache=None):
            if stage != engine.RPE or wires != jobs:
                raise ValueError("Grade request differs from the frozen bridge")
            return engine.stage(stage, wires, identity, True, ledger, cache)

        engine.grade_rpe(roots, rows, dispatch)
        probe.freeze(OUT / "RESULTS.json", {"rows": rows, "ledger": ledger})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    main(parser.parse_args().action)
