"""Grade saved RP-Reasoner PersistBench answers in the existing matched Judge lane."""
from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
from pathlib import Path

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha

import run_v41 as runtime
from transfer_replay import C5, GATE, PERSIST_CONTROLS, RP, STAGE, development, persist, read, run as replay

OUT = runtime.OUT.with_name("persist_rp_score_alignment_v1")
RUN = runtime.RUN.with_name(OUT.name)
PROBE = runtime.probe
EVALUATOR = persist.author.ext.parent.persist
FLAGS = ("failure_release", "failure_strict_utility")


def prepare():
    audit = replay()["persistbench"]
    if audit["archived_roots"] != 60 or len(audit["cases"]) != 58 or audit["RP_gpt41_exact_cache"]:
        raise ValueError("PersistBench RP transfer inventory changed")
    author_plan = read(persist.AUTHOR_OUT / "PLAN.json")
    controls = {case["uid"]: case for case in author_plan["cases"] if case["role"] == "DEV"}
    by_uid = {case["uid"]: case for case in read(development.OUT / "PLAN.json")["cases"]
              if case["uid"] in controls}
    rows = {row["uid"]: row for row in read(development.OUT / "RESULT_ROWS.json")
            if row["uid"] in by_uid and row["method"] == RP}
    _, rubrics, fmt = EVALUATOR.upstream()
    protocol = deepcopy(author_plan["protocols"]["gpt41"])
    protocol.update(namespace=f"{OUT.parent.name}/{OUT.name}", stream_cooldown_seconds=60)
    if protocol["model"] != "gpt-4.1" or protocol["stages"][STAGE] != {"temperature": 0, "max_tokens": 4096}:
        raise ValueError("Use the original matched Judge parameters")
    tasks, units = [], []
    for ref in audit["cases"]:
        uid, category = ref["uid"], ref["category"]
        task, saved = development.task_for(by_uid[uid]), rows[uid]
        if category != controls[uid]["category"] or saved["actor_status"] != "OK":
            raise ValueError("RP evidence category or answer changed")
        request = persist.author.ext.text_request(
            rubrics[category], fmt["build_judge_prompt"]([m.text for m in task.memories], task.query, saved["answer"]),
            protocol["model"], protocol["stages"][STAGE]["max_tokens"],
        )
        validate_public_request(request)
        if sha(request) != ref["RP_gpt41_request_sha256"]:
            raise ValueError("Request differs from the previously verified matched scoring wire")
        units.append({"request": request, "unit": {"stage": STAGE, "method": RP, "replicate": 0, "root_id": uid,
                                                   "protocol_sha256": sha(protocol)}})
        tasks.append({**ref, "actor_sha256": saved["actor_request_sha256"], "answer_sha256": sha(saved["answer"])})
    if len({sha(item["request"]) for item in units}) != len(units):
        raise ValueError("Unexpected duplicated score request in PersistBench")
    return {
        "targets": tasks, "unavailable_archived_RP_uids": sorted(controls.keys() - {row["uid"] for row in tasks}),
        "physical_cap": len(units), "code_sha256": sha(Path(__file__).read_bytes()),
        "service_reference_sha256": author_plan["service_reference_sha256"], "no_new_generation": True,
        "batches": {"smoke": {"protocol": protocol, "units": units[:4]},
                    "panel": {"protocol": protocol, "units": units[4:]}},
    }


def configure(batch):
    PROBE.OUT, PROBE.RUN = OUT / batch, RUN / batch


def parse_scores(plan):
    witnessed = {}
    for phase in plan["batches"]:
        configure(phase)
        path = PROBE.OUT / (STAGE + "_MANIFEST.json")
        if path.exists() and read(path) != plan["batches"][phase]:
            raise ValueError("Recorded manifest changed")
        witnessed.update(PROBE.stage_receipts(STAGE))
    scores = []
    for case in plan["targets"]:
        rec, raw = witnessed.get((case["uid"], RP), (None, None))
        row = {**case, "receipt": rec, "score": None, "raw_score": raw,
               "status": rec["status"] if rec else "UNISSUED"}
        if raw is not None:
            try:
                row["score"] = EVALUATOR.score(case["category"], raw)
            except (ValueError, TypeError, KeyError) as error:
                row.update(status="INVALID_NATIVE_SCORE", score_error=str(error))
        scores.append(row)
    return scores


def report(plan):
    authors = {(row["uid"], row["method"]): row["score"]
               for wave in sorted((persist.AUTHOR_OUT / "waves").glob("*.json"))
               for row in read(wave)["rows"] if row["method"] in PERSIST_CONTROLS}
    authors.update({(row["uid"], row["method"]): row["score"]
                    for row in read(persist.OUT / "RESULTS.json")["rows"] if row["method"] in (C5, GATE)})
    rows = parse_scores(plan)
    stats = {}
    for method in (*PERSIST_CONTROLS, C5, GATE):
        for category in sorted({row["category"] for row in rows}):
            for flag in FLAGS:
                t = stats[method, category, flag] = Counter()
                for row in rows:
                    if category != row["category"]:
                        continue
                    other = authors.get((row["uid"], method))
                    listed = method in row["matched_author_controls"] + row["matched_in_house_controls"]
                    if listed != (other is not None):
                        raise ValueError("Matched saved control lost its audit receipt")
                    if other is None:
                        continue
                    t["eligible_comparator"] += 1
                    if row["score"] is not None:
                        a, b = int(row["score"][flag]), int(other[flag])
                        t.update(common=1, RP=a, comparator=b, RP_only_failure=a and not b,
                                 comparator_only_failure=b and not a)
    receipts = [row["receipt"] for row in rows if row["receipt"] is not None]
    return {
        "coverage": Counter(row["status"] for row in rows),
        "valid_native": sum(row["score"] is not None for row in rows),
        "physical": len(receipts), "cap": plan["physical_cap"],
        "tokens": sum((rec["usage"] or {}).get("total_tokens", 0) for rec in receipts),
        "unknown_usage": sum("total_tokens" not in (rec["usage"] or {}) for rec in receipts),
        "retries": sum(rec["automatic_retries"] for rec in receipts),
        "comparisons": [{"method": m, "category": c, "metric": f, **n} for (m, c, f), n in stats.items()],
        "not_independent_confirmation": True, "new_generation": 0, "old_scores_changed": 0,
        "unavailable_archived_RP_uids": plan["unavailable_archived_RP_uids"], "rows": rows,
    }


def run(plan):
    if prepare() != plan or PROBE.read_reference()[1] != plan["service_reference_sha256"]:
        raise ValueError("PersistBench replay or service drifted from the freeze")
    state = OUT / "RUN_STATE.json"
    for name, manifest in plan["batches"].items():
        PROBE.atomic_json(state, {"state": "RUNNING", "batch": name})
        configure(name)
        PROBE.freeze(PROBE.OUT / (STAGE + "_MANIFEST.json"), manifest)
        try:
            runtime.dispatch(plan, STAGE, manifest)
            if any(record is None for record, _ in PROBE.stage_receipts(STAGE).values()):
                raise RuntimeError("Some registered jobs remain undispatched")
            if name == "smoke" and report(plan)["valid_native"] < 2:
                raise RuntimeError("Scoring contract failed on smoke")
        except (RuntimeError, ValueError, KeyError) as error:
            PROBE.atomic_json(state, {"state": "STOPPED", "batch": name, "error": str(error)})
            raise
    PROBE.atomic_json(state, {"state": "COMPLETE"})


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    action = parser.parse_args().action
    path = OUT / "FROZEN.json"
    if action == "report":
        result = report(read(path))
        PROBE.atomic_json(OUT / "RESULTS.json", result)
        print({key: val for key, val in result.items() if key not in ("rows", "comparisons")})
        return
    with PROBE.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            plan = prepare()
            PROBE.freeze(path, plan)
            print(f"Frozen {plan['physical_cap']} scoring-only requests")
        else:
            run(read(path))


if __name__ == "__main__":
    main()
