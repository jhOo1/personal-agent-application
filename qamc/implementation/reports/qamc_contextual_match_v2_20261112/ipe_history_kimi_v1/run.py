"""Fixed-history-route model substitution, with an eligibility stage and score reuse."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "native_residual_v1"))

from audit_rpe_fixed_route_actor import add_pair
from incremental_panel import prior, read, sha
from run_probe import engine, probe

MODEL = "kimi-k3.1-pro"
METHOD = "IPE_C_KIMI_ACTOR"
STAGE = "KimiHistoryActor"
SMOKE = "KimiHistoryActorSmoke"
SMOKE_JUDGE = "RPEvalJudgeSmoke"
RP = "RPR_PAPER_FULL"
RUN = engine.RUN.with_name(HERE.name)
FROZEN = RUN / "FROZEN.json"
QUOTAS = {"history_C": 4, "history_B": 4, "history_all_A": 2}


def prepare():
    v41 = prior.R["archived"].v41
    formal = read(v41.formal.OUT / "PLAN.json")["cases"]
    cases = {r["uid"]: r for r in formal}
    if len(cases) != 300 or any(r["independent_confirmation"] is not False for r in formal):
        raise ValueError("The original exposed development plan is required")
    archive = {r["uid"]: r for r in read(v41.formal.OUT / "RESULT_ROWS.json") if r["method"] == RP}
    prior_panel = read(BASE / "native_residual_v1/RPE_FIXED_ROUTE_ACTOR_PANEL.json")["cases"]
    used_uids = {r["uid"] for r in prior_panel}
    used_groups = {r["source_group"] for r in prior_panel}
    original = read(BASE / "ipe_c_two_endpoint_completion_v1/RESULTS.json")["rows"]
    candidates = defaultdict(list)
    for row in original:
        uid, labels = row["uid"], row["labels"]
        grade = row["ipe_c"]["grade"]
        if row["old_route"] != "REUSE_RP" or not grade.get("match") or not labels:
            continue
        group = cases[uid]["analysis_group_id"]
        if group != row["source_group"] or len(labels) != grade["match"]["positions"]:
            raise ValueError("Source group or denominator changed")
        key = "history_C" if "C" in labels else "history_B" if "B" in labels else "history_all_A"
        candidates[key].append((row, group))

    jobs, roots, panel, selected_groups = {}, {}, [], set()
    for key in ("history_B", "history_all_A", "history_C"):
        count = 0
        for row, group in sorted(candidates[key], key=lambda x: (
                x[1] in used_groups, x[0]["uid"] in used_uids, sha(["fixed-kimi-history-v1", x[0]["uid"]]))):
            if group in selected_groups:
                continue
            uid = row["uid"]
            ref = archive[uid]
            wire = ref["actor_request"]
            if (ref["actor_status"] != "OK" or sha(wire) != ref["actor_request_sha256"]
                    or wire["model"] != "qwen3.8-flash"
                    or sha(ref["answer"]) != row["ipe_c"]["answer_sha256"]):
                raise ValueError("Stored Actor input or output changed")
            packet = json.loads(wire["messages"][1]["content"])
            roots[uid] = {"original_sources": packet["source_evidence"], "archived": {}}
            smoke = key != "history_all_A" and count == 0
            panel.append({"uid": uid, "source_group": group, "stratum": key,
                          "qwen_request_sha256": sha(wire), "qwen_answer_sha256": sha(ref["answer"]),
                          "base_grade": row["ipe_c"]["grade"], "smoke": smoke,
                          "prior_backbone_group": group in used_groups, "prior_backbone_uid": uid in used_uids})
            jobs[uid, METHOD] = {**wire, "model": MODEL}
            selected_groups.add(group)
            count += 1
            if count == QUOTAS[key]:
                break
        if count != QUOTAS[key]:
            raise ValueError(f"Missing source diversity in {key}: {count}")
    return {"cases": panel, "wire_hashes": [sha(wire) for wire in jobs.values()],
            "quotas": QUOTAS, "model": MODEL, "code_sha256": sha(Path(__file__).read_bytes()),
            "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes())}, jobs, roots


def run(plan, jobs, roots, phase):
    if plan != read(FROZEN):
        raise ValueError("Frozen panel drift")
    engine.OUT = probe.OUT = RUN
    probe.RUN = RUN
    engine.CAP = {SMOKE: 2, SMOKE_JUDGE: 2, STAGE: 8, engine.RPE: 8}
    identity = {"service_reference_sha256": probe.read_reference()[1], "experiment_sha256": sha(plan)}
    is_smoke = phase == "smoke"
    if not is_smoke:
        first = read(RUN / "SMOKE_RESULTS.json")["rows"]
        if len(first) != 2 or not all((r["score"] or {}).get("match") for r in first):
            raise ValueError("Two strict smoke results are necessary to expand")
    cards = {r["uid"]: r for r in plan["cases"] if r["smoke"] == is_smoke}
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)

        def dispatch(stage, wires, cache=None):
            if is_smoke and stage == engine.RPE:
                stage = SMOKE_JUDGE
            return engine.stage(stage, wires, identity, True, ledger, cache)

        generated = dispatch(SMOKE if is_smoke else STAGE, {k: v for k, v in jobs.items() if k[0] in cards})
        rows = [{"uid": uid, "method": method, "actor_status": value["status"], "answer": value["answer"],
                 "base_score": cards[uid]["base_grade"], "score": None, "stratum": cards[uid]["stratum"]}
                for (uid, method), value in generated.items()]
        engine.grade_rpe(roots, rows, dispatch)
        probe.freeze(RUN / ("SMOKE_RESULTS.json" if is_smoke else "PILOT_RESULTS.json"),
                     {"rows": rows, "ledger": ledger})


def summarize():
    comparisons = defaultdict(Counter)
    receipts = []
    for phase in ("SMOKE", "PILOT"):
        path = RUN / f"{phase}_RESULTS.json"
        if not path.exists():
            continue
        result = read(path)
        receipts.extend(result["ledger"])
        for row in result["rows"]:
            for subset in ("all", row["stratum"]):
                add_pair(comparisons[subset], row["score"], row["base_score"])
    return {"comparisons": comparisons, "recorded_calls": len(receipts),
            "status": Counter(r["status"] for r in receipts),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in receipts),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in receipts)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "check", "smoke", "pilot", "summary"))
    action = parser.parse_args().action
    if action == "summary":
        print(json.dumps(summarize(), indent=2))
    else:
        plan, jobs, roots = prepare()
        if action == "freeze":
            probe.freeze(FROZEN, plan)
        elif action == "check":
            if plan != read(FROZEN):
                raise ValueError("Frozen panel drift")
            print(json.dumps({"strata": Counter(r["stratum"] for r in plan["cases"]), "sha256": sha(plan)}))
        else:
            run(plan, jobs, roots, action)
