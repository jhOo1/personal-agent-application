"""Extend exact IPE-C across the already exposed archived RPEval panel."""
import argparse
from collections import Counter
import json
from pathlib import Path

from census import BASE, prior, read, sha
from qamc.common import parse_object
from qamc_rpeval_terminal_judge_sensitivity import inspect
from score_task_only import OUT as ZERO_OUT, saved_drafts

HERE = Path(__file__).resolve().parent
v41 = prior.R["archived"].v41
engine, probe = prior.engine, prior.probe
RP, GATE, ZERO = v41.RP, v41.GATE, "TASK_ONLY"
DRAFT = "TaskDraft"
METRICS = ("OPB", "UPB", "FM")


def index(rows):
    return {r["uid"]: r for r in rows}


def source_root(row, rank):
    wire = row["actor_request"]
    digest = sha(wire)
    fused = rank["policies"]["PAPER_FUSION"]
    if digest != row["actor_request_sha256"] or digest != fused["actor_request_sha256"] or not fused["archived_actor_wire_unchanged"]:
        raise ValueError("Rank replay does not match the exact RP Actor request")
    packet = json.loads(wire["messages"][1]["content"])
    return {"archived_actor_request": wire, "archived_actor_sha256": digest,
            "public_task": {k: packet[k] for k in ("query", "current_context", "facts")},
            "original_sources": packet["source_evidence"], "archived_policy": packet["preference_use_policy"]}


def prepare():
    original = read(v41.formal.OUT / "PLAN.json")
    cases = v41.author_cases(original)
    if len(cases) != 300 or any(r["independent_confirmation"] for r in original["cases"]):
        raise ValueError("Require the complete already exposed formal-development panel")
    path = v41.OUT / "FROZEN.json"
    old = read(path)
    if old["independent_confirmation"]:
        raise ValueError("Previously exposed task-only archive expected")
    old_ids = {r["uid"] for r in old["roots"]}
    old_ranks = index(read(BASE / "rp_estimator_routing_replay_v1/RESULTS.json")["rows"])
    old_z = index(read(ZERO_OUT / "RESULTS.json")["roots"])
    old_zero_inputs = read(ZERO_OUT / "FROZEN.json")["ready"]
    saved = saved_drafts(old)
    formal_rows = read(v41.formal.OUT / "RESULT_ROWS.json")
    archived = {(row["uid"], row["method"]): row for row in formal_rows
                if row["uid"] in cases and row["method"] in (RP, GATE, "MEMADAPTER_FULL", "DES2GEN_FULL")}
    rank = index(read(v41.formal.OUT / "RPR_RANK_FUSION_AUDIT_300.json")["rows"])
    jobs, rows = {}, []
    for uid, case in cases.items():
        ref = archived[uid, RP]
        row = {"uid": uid, "source_group": case["analysis_group_id"], "track": case["track"],
               "scope": "previous_233" if uid in old_ids else "additional_67"}
        if uid not in rank or ref["actor_status"] != "OK":
            rows.append({**row, "disposition": "ARCHIVED_ESTIMATE_OR_ACTOR_UNAVAILABLE"})
            continue
        request = v41.task_only_request(source_root(ref, rank[uid]))
        draft_hash = sha(request)
        keep = "C" in rank[uid]["policies"]["IPE_ONLY"]["policy"]
        if uid in old_ids:
            if keep != old_ranks[uid]["keep_rp"]["IPE_C"]:
                raise ValueError("Original IPE-C branch drift")
            old_input = old_zero_inputs.get(uid)
            if old_input and old_input["task_wire_sha256"] != draft_hash:
                raise ValueError("Original IPE-C wire drift")
        if keep:
            disposition = "REUSE_RP"
        elif uid in old_ids:
            disposition = "REUSE_ORIGINAL_TASK_ONLY_STATE"
        elif draft_hash in saved:
            disposition = "REUSE_DRAFT" if saved[draft_hash]["answer"] else "ARCHIVED_DRAFT_FAILED"
        else:
            disposition = "NEW_DRAFT"
            jobs[uid, ZERO] = request
        rows.append({**row, "disposition": disposition, "task_only_request_sha256": draft_hash})
    plan = {"rows": rows, "draft_wires": [[uid, method, wire] for (uid, method), wire in jobs.items()],
            "judge_cap": sum(r["disposition"] in ("REUSE_DRAFT", "NEW_DRAFT") for r in rows),
            "prior_v41_hash": sha(path.read_bytes()),
            "formal_panel_sha256": sha(original), "code_sha256": sha(Path(__file__).read_bytes())}
    return plan, cases, original, archived, rank, old_z, saved, old_zero_inputs


def entry(row, answer, fields, raw, labels):
    result = {"answer_sha256": sha(answer) if answer else None, "grade": fields, "flags": None}
    if fields.get("match") and raw and labels:
        result["flags"] = inspect({"uid": row["uid"], "method": "IPE_C", "answer": answer,
                                   "native_fields": fields, "raw_scores": {v41.NATIVE: raw}}, labels)["flags"]
    return result


def pair(rows, method, clean=False):
    matched, groups = Counter(), set()
    for row in rows:
        a, b = row["ipe_c"], row["controls"][method]
        if not a["grade"].get("match") or not b["grade"].get("match"):
            continue
        if clean and (a["flags"] != [] or b["flags"] != []):
            continue
        x, y = a["grade"]["match"], b["grade"]["match"]
        if x["positions"] != y["positions"] or x["positions"] != len(row["labels"]):
            raise ValueError("Incompatible native positions")
        matched.update(tasks=1, positions=x["positions"], ipe_match=x["matched"], control_match=y["matched"],
                       ipe_wins=x["matched"] > y["matched"], ipe_losses=x["matched"] < y["matched"],
                       ipe_full=x["matched"] == x["positions"], control_full=y["matched"] == y["positions"])
        groups.add(row["source_group"])
        for m in METRICS:
            if m in a["grade"] and m in b["grade"]:
                matched.update({m + "_pairs": 1, "ipe_" + m: a["grade"][m], "control_" + m: b["grade"][m]})
    return {**matched, "groups": len(groups)}


def run(action, data):
    plan, cases, original, archived, ranks, old_z, saved, old_zero_inputs = data
    probe.OUT = engine.OUT = HERE
    probe.RUN = engine.RUN.with_name(HERE.name)
    engine.CAP = {DRAFT: len(plan["draft_wires"]), engine.RPE: plan["judge_cap"]}
    identity = {"experiment_sha256": sha(plan), "service_reference_sha256": probe.read_reference()[1]}
    ledger, rows, live = [], [], action == "run"

    def stage(name, jobs, cache=None):
        return engine.stage(name, jobs, identity, live, ledger, cache) if jobs else {}

    with probe.runner_lock(probe.RUN / "runner.lock"):
        probe.freeze(HERE / "EXECUTION.json", identity)
        drafts = stage(DRAFT, {(uid, method): wire for uid, method, wire in plan["draft_wires"]})
        pending, cache = {}, {}
        for uid, p in old_zero_inputs.items():
            raw = old_z[uid]["task_only"]["raw"]
            if raw:
                digest = p["graded_wire_sha256"]
                previous = cache.setdefault(digest, raw)
                if previous != raw:
                    raise ValueError("Conflicting archived task-only grades")
        completed_grades = set(cache)
        controls = (RP, GATE, "MEMADAPTER_FULL", "DES2GEN_FULL")
        for spec in plan["rows"]:
            uid, mode = spec["uid"], spec["disposition"]
            labels = ranks.get(uid, {}).get("author_labels") or old_z.get(uid, {}).get("labels")
            row = {**spec, "labels": labels, "controls": {}}
            rows.append(row)
            base = archived[uid, RP]
            ans, fields, raw = None, {}, None
            for m in controls:
                old = archived[uid, m]
                row["controls"][m] = entry(row, old.get("answer"), old.get("native_fields") or {},
                                            old["raw_scores"].get(v41.NATIVE), labels)
            if mode == "REUSE_RP":
                ans, fields, raw = base["answer"], base["native_fields"], base["raw_scores"].get(v41.NATIVE)
            elif mode == "REUSE_ORIGINAL_TASK_ONLY_STATE":
                old_grade = old_z[uid]["task_only"]
                stored = saved.get(spec["task_only_request_sha256"])
                ans = stored["answer"] if stored else None
                fields, raw = old_grade["fields"], old_grade["raw"]
                row["original_task_only_status"] = old_grade["status"]
            elif mode in ("REUSE_DRAFT", "NEW_DRAFT"):
                key = spec["task_only_request_sha256"]
                receipt = saved[key] if mode == "REUSE_DRAFT" else drafts[uid, ZERO]
                ans = receipt["answer"]
                if mode == "NEW_DRAFT":
                    row["new_generation_status"] = receipt["status"]
                if ans:
                    judge_wire = engine.rpe_wire(original, cases[uid],
                                                 {"uid": uid, "answer": ans, "actor_status": "OK"})
                    for m in controls:
                        old = archived[uid, m]
                        old_raw = old["raw_scores"].get(v41.NATIVE)
                        if old.get("answer") == ans and old_raw and old.get("actor_status") == "OK":
                            old_wire = engine.rpe_wire(original, cases[uid], old)
                            if old_wire != judge_wire:
                                raise ValueError("Same answer did not reconstruct the same Judge request")
                            previous = cache.setdefault(sha(judge_wire), old_raw)
                            if previous != old_raw:
                                raise ValueError("Conflicting saved exact score")
                    row["used_prior_task_only_judge"] = sha(judge_wire) in completed_grades
                    pending[uid, ZERO] = judge_wire
            row["answer"], row["ipe_c"] = ans, entry(row, ans, fields or {}, raw, labels)
        answers = stage(engine.RPE, pending, cache)
        for row in rows:
            if reply := answers.get((row["uid"], ZERO)):
                row["judge"] = reply
                fields = {}
                if reply["status"] == "OK":
                    try:
                        fields, row["invalid"] = probe.fields(parse_object(reply["answer"]), len(row["labels"]), True)
                    except (KeyError, TypeError, ValueError) as exc:
                        row["invalid"] = str(exc)
                row["ipe_c"] = entry(row, row["answer"], fields, reply["answer"], row["labels"])
        slices = {"all_300": rows, "additional_67": [r for r in rows if r["scope"] == "additional_67"],
                  "all_A": [r for r in rows if r["labels"] and set(r["labels"]) == {"A"}],
                  "only_B": [r for r in rows if r["labels"] and "B" in r["labels"] and "C" not in r["labels"]],
                  "contains_C": [r for r in rows if r["labels"] and "C" in r["labels"]]}
        result = {"rows": rows, "dispositions": Counter(r["disposition"] for r in rows),
                  "metrics": {key: {m: {"raw": pair(scope, m), "flag_excluded": pair(scope, m, True)}
                                    for m in controls} for key, scope in slices.items()},
                  "calls": Counter(r["unit"]["stage"] for r in ledger), "ledger": ledger,
                  "tokens": sum((r["usage"] or {}).get("total_tokens") or 0 for r in ledger),
                  "usage_unknown": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}
        path = HERE / "RESULTS.json"
        if live:
            probe.freeze(path, result)
        elif read(path) != result:
            raise ValueError("Expanded IPE-C baseline replay mismatch")
        print({k: result[k] for k in ("dispositions", "calls", "tokens", "usage_unknown")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run", "replay"))
    action = parser.parse_args().action
    data = prepare()
    plan = data[0]
    path = HERE / "FROZEN.json"
    if action == "freeze":
        probe.freeze(path, plan)
    elif read(path) != plan:
        raise SystemExit("Panel or implementation drifted")
    elif action != "check":
        run(action, data)
    print({"additional": Counter(r["disposition"] for r in plan["rows"] if r["scope"] == "additional_67"),
           "draft_cap": len(plan["draft_wires"]), "judge_cap": plan["judge_cap"]})
