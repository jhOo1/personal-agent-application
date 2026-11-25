"""Grade the saved V41 task-only drafts without regenerating answers."""
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

from qamc.common import parse_object, sha
from proposals.qamc_protocol_alignment.sampling import validate_public_request

import run_v41 as v41
from analyze import metric_pairs, paired
from audit_completed import audited_rows

METHOD = "TASK_ONLY"
OUT = v41.OUT.with_name("counterfactual_rpeval_v41_task_only")
RUN = v41.RUN.with_name(OUT.name)
PROBE = v41.probe
READ = v41.read


def saved_drafts(plan):
    drafts = {}
    for i, _ in enumerate(plan["waves"]):
        wave = f"wave_{i:02d}"
        folder = v41.OUT / wave
        manifest = READ(folder / (v41.DRAFT + "_MANIFEST.json"))
        staged = {sha(item["request"]): item for item in manifest["units"]}
        wave_drafts = READ(folder / "DRAFT_RESULTS.json")
        if staged.keys() != wave_drafts.keys() or staged.keys() & drafts.keys():
            raise ValueError("Saved draft inventory changed")
        PROBE.OUT, PROBE.RUN = folder, v41.RUN / wave
        receipts = PROBE.stage_receipts(v41.DRAFT)
        for digest, saved in wave_drafts.items():
            unit = staged[digest]["unit"]
            if saved["uid"] != unit["root_id"] or (
                saved["record"], saved["answer"]
            ) != receipts[saved["uid"], unit["method"]]:
                raise ValueError("Saved task-only draft no longer matches transport receipt")
        drafts.update(wave_drafts)
    return drafts


def prepare():
    plan_path = v41.OUT / "FROZEN.json"
    terminal_path = v41.OUT / "TERMINAL.json"
    plan, terminal = READ(plan_path), READ(terminal_path)
    if not terminal["primary_panel"]["complete"] or terminal["frozen_sha256"] != sha(plan_path.read_bytes()):
        raise ValueError("Require the settled V41 panel")
    original = READ(v41.formal.OUT / "PLAN.json")
    cases = v41.author_cases(original)
    drafts = saved_drafts(plan)
    ready, missing, wires, terminal_scores = {}, {}, {}, {}
    for rows, _ in audited_rows(plan):
        terminal_scores.update({row["uid"]: row for row in rows})
    reused_answers = {}
    for root in plan["roots"]:
        uid, expected = root["uid"], root["task_wire_sha256"]
        wire = v41.task_only_request(root)
        if uid not in cases or sha(wire) != expected:
            raise ValueError("Task only request outside verified exposed panel")
        draft = drafts[expected]
        if not draft["answer"]:
            missing[uid] = draft["record"]["status"] if draft["record"] else "NO_DRAFT_RECEIPT"
            continue
        answer = draft["answer"]
        answer_row = {"uid": uid, "method": v41.GATE, "actor_status": "OK", "answer": answer}
        item, = v41.formal.grading_jobs(original, [cases[uid]], [answer_row])
        grade = item["request"]
        validate_public_request(grade)
        grade_hash = sha(grade)
        row = terminal_scores[uid]
        ready[uid] = {"task_wire_sha256": expected, "answer_sha256": sha(answer),
                      "graded_wire_sha256": grade_hash, "draft_origin_uid": draft["uid"],
                      "positions": len(row["labels"])}
        originals = {m: item["answer"] for m, item in root["archived"].items()}
        originals.update({m: item["answer"] for m, item in row["answers"].items()})
        prior = next((method for method, text in originals.items()
                      if text == answer and row["native"][method]["raw"] is not None), None)
        if prior is not None:
            reused_answers[uid] = prior
        else:
            wires.setdefault(grade_hash, (uid, METHOD, grade))
    settled_missing = {entry["method"]: entry["count"] for entry in terminal["answer_status"]
                       if entry["status"] == "NO_USABLE_DRAFT"}
    if (set(ready) | set(missing) != set(terminal_scores)
            or any(settled_missing.get(method, 0) != len(missing) for method in v41.ARMS)):
        raise ValueError("Task-only scoring does not cover settled draft statuses")
    waves = {}
    for i, uids in enumerate(plan["waves"]):
        wave = f"wave_{i:02d}"
        items = [wires[ready[uid]["graded_wire_sha256"]] for uid in uids
                 if uid in ready and uid not in reused_answers
                 and wires[ready[uid]["graded_wire_sha256"]][0] == uid]
        if items and "smoke" not in waves:
            waves["smoke"] = v41.manifest(f"{OUT.name}/smoke", v41.NATIVE, items[:4])
            items = items[4:]
        if items:
            waves[wave] = v41.manifest(f"{OUT.name}/{wave}", v41.NATIVE, items)
    return {"source_sha256": sha(terminal_path.read_bytes()), "stage": v41.NATIVE,
            "code_sha256": sha(Path(__file__).read_bytes()), "ready": ready, "missing": missing,
            "reused_answers": reused_answers, "waves": waves,
            "maximum_new_grade_requests": len(wires), "new_actor_requests": 0,
            "service_reference_sha256": plan["service_reference_sha256"]}


def collect(plan):
    original = READ(v41.OUT / "FROZEN.json")
    physical = {}
    for wave, manifest in plan["waves"].items():
        PROBE.OUT, PROBE.RUN = OUT / wave, RUN / wave
        path = PROBE.OUT / (v41.NATIVE + "_MANIFEST.json")
        if not path.exists():
            continue
        if READ(path) != manifest:
            raise ValueError("New scoring manifest differs from frozen contract")
        for record, raw in PROBE.stage_receipts(v41.NATIVE).values():
            if record is not None:
                physical[record["request_sha256"]] = (record, raw)
    rows = []
    for batch, _ in audited_rows(original):
        for row in batch:
            uid = row["uid"]
            entry = {"status": "UNISSUED", "fields": {}, "raw": None}
            if uid in plan["missing"]:
                entry["status"] = "NO_USABLE_DRAFT"
            elif uid in plan["reused_answers"]:
                prior = plan["reused_answers"][uid]
                entry.update(row["native"][prior], status="EXACT_ARCHIVED_SCORE", reuse=prior)
            else:
                digest = plan["ready"][uid]["graded_wire_sha256"]
                record, raw = physical.get(digest, (None, None))
                if record is not None:
                    entry.update(status=record["status"], raw=raw)
                if raw is not None:
                    try:
                        entry["fields"], entry["invalid"] = PROBE.fields(parse_object(raw), len(row["labels"]), True)
                    except (ValueError, KeyError, TypeError) as error:
                        entry.update(status="INVALID_JUDGE_OUTPUT", invalid=str(error))
            row["native"][METHOD] = entry
            row["positions"] = len(row["labels"])
            rows.append(row)
    return rows, [record for record, _ in physical.values()]


def summarize(plan):
    rows, ledger = collect(plan)
    subsets = {
        "all": rows,
        "all_A": [row for row in rows if set(row["labels"]) == {"A"}],
        "contains_BC": [row for row in rows if set(row["labels"]) != {"A"}],
        "less_exposed": [row for row in rows if row["in_sensitivity"]],
        "additional_groups": [row for row in rows if not row["in_sensitivity"]],
    }
    comparisons = {}
    for name, subset in subsets.items():
        comparisons[name] = {}
        for comparator in (v41.GATE, v41.RP, *v41.ARMS):
            comparisons[name][comparator] = {
                **paired(subset, METHOD, comparator),
                "separate_metric_pairs": metric_pairs(subset, METHOD, comparator),
            }
    return {
        "state": READ(OUT / "RUN_STATE.json") if (OUT / "RUN_STATE.json").exists() else {"state": "FROZEN"},
        "planned_roots": len(rows), "prior_answers_reused_for_scoring": len(plan["ready"]),
        "physical_requests": len(ledger), "physical_cap": plan["maximum_new_grade_requests"],
        "task_only_root_status": Counter(row["native"][METHOD]["status"] for row in rows),
        "task_only_valid_native_match": sum("match" in row["native"][METHOD]["fields"] for row in rows),
        "comparisons": comparisons, "roots": [
            {"uid": row["uid"], "group": row["group"], "labels": row["labels"],
             "task_only": row["native"][METHOD]} for row in rows
        ],
        "ledger": ledger, "score_changes": 0, "new_actor_requests": 0,
    }


def run(plan, smoke_only):
    if prepare() != plan:
        raise ValueError("Scoring freeze no longer matches archive and code")
    if PROBE.read_reference()[1] != plan["service_reference_sha256"]:
        raise ValueError("Scoring service reference changed")
    for wave, manifest in plan["waves"].items():
        PROBE.OUT, PROBE.RUN = OUT / wave, RUN / wave
        PROBE.atomic_json(OUT / "RUN_STATE.json", {"state": "RUNNING", "wave": wave})
        PROBE.freeze(PROBE.OUT / (v41.NATIVE + "_MANIFEST.json"), manifest)
        try:
            v41.dispatch(plan, v41.NATIVE, manifest)
            receipts = PROBE.stage_receipts(v41.NATIVE)
            if any(record is None for record, _ in receipts.values()):
                raise RuntimeError("A planned scoring request remains undispatched")
            if wave == "smoke":
                valid = 0
                for (uid, _), (_, raw) in receipts.items():
                    if raw:
                        try:
                            fields, _ = PROBE.fields(parse_object(raw), plan["ready"][uid]["positions"], True)
                        except (ValueError, TypeError, KeyError):
                            continue
                        valid += "match" in fields
                if valid < min(2, len(receipts)):
                    raise RuntimeError("Scoring smoke returned fewer than two valid native scores")
        except (ValueError, RuntimeError, TypeError, KeyError) as error:
            PROBE.atomic_json(OUT / "RUN_STATE.json", {"state": "STOPPED", "wave": wave, "error": str(error)})
            raise
        if smoke_only:
            PROBE.atomic_json(OUT / "RUN_STATE.json", {"state": "SMOKE_COMPLETE", "wave": wave})
            return
    PROBE.atomic_json(OUT / "RUN_STATE.json", {"state": "COMPLETE", "waves": len(plan["waves"])})


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "smoke", "run", "report"))
    action = parser.parse_args().action
    path = OUT / "FROZEN.json"
    if action == "report":
        report = summarize(READ(path))
        PROBE.atomic_json(OUT / "RESULTS.json", report)
        print({key: value for key, value in report.items() if key not in ("roots", "comparisons", "ledger")})
        return
    with PROBE.runner_lock(RUN / "runner.lock"):
        if action == "freeze":
            plan = prepare()
            PROBE.freeze(path, plan)
            print(f"{len(plan['ready'])} saved answers, {plan['maximum_new_grade_requests']} new scoring calls maximum")
        else:
            run(READ(path), smoke_only=action == "smoke")


if __name__ == "__main__":
    main()
