"""Run an equal-budget comparison of open-condition planning and generic planning."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import sha

import open_condition_planning as method
import run_asymmetric_fusion as fusion
from settle_joint_planning import usage


BASE = fusion.OUT.with_name("open_condition_rpeval_v1")
RUN = fusion.RUN.with_name(BASE.name)
GOALS, ACTOR, JUDGE = "OpenConditionSelector", "OpenConditionActor", fusion.JUDGE
SHARED = "SHARED_GOALS"
GATE = fusion.active.outcome.GATE
probe, read, runtime, replay, scorer = fusion.probe, fusion.read, fusion.runner, fusion.replay, fusion.scorer


def review_cases(roots):
    archive = BASE.parent / "linked_decision_rpeval_v1" / "SETTLED.json"
    linked = {r["uid"]: r for r in read(archive)["rows"]}
    manifest = []
    for suffix, mid, cite, answer, action in read(BASE / "PREFLIGHT_CASES.json"):
        uid, = (uid for uid in roots if uid.endswith(suffix))
        root = roots[uid]
        source, = (item for item in root["original_sources"] if item["memory_id"] == mid)
        if not any(cite in p for p in method.user_source(source["text"])) or answer not in linked[uid]["outputs"]["LINKS_OFF"]:
            raise ValueError("A preflight witness does not match the public archive")
        manifest.append({"uid": uid, "group": root["group"], "task_sha256": sha(root["public_task"]),
                         "source_id": mid, "source_quote": cite, "prior_answer_quote": answer, "possible_action": action})
    if len({x["task_sha256"] for x in manifest}) < 10 or len({x["group"] for x in manifest}) < 6:
        raise ValueError("Insufficient distinct development opportunities")
    return manifest, sha(archive.read_bytes())


def prepare(reference, phase):
    _, _, _, roots, (archive, official, cases), inherited = fusion.prepare(reference)
    diagnostics, digest = review_cases(roots)
    protected = []
    seen = {item["group"] for item in diagnostics}
    for uid in sorted(roots, key=lambda key: sha(["open_condition_v1_protection", key])):
        group = roots[uid]["group"]
        if group not in seen:
            protected.append(uid)
            seen.add(group)
        if len(protected) == 4:
            break
    smoke = {row["uid"] for row in diagnostics} | set(protected)
    selected = {uid: root for uid, root in roots.items() if (uid in smoke) == (phase == "smoke")}
    jobs = [(uid, SHARED, method.goal_request(root["public_task"], root["original_sources"]))
            for uid, root in selected.items()]
    rows = {uid: {key: archive[uid][key] for key in ("uid", "group", "labels", "positions", "native")}
            for uid in selected}
    cache = {GOALS: {}, ACTOR: {}, JUDGE: inherited[JUDGE]}
    names = (Path(__file__), Path(method.__file__), Path(fusion.__file__),
             BASE / "PREFLIGHT_CASES.json", BASE / "PROTOCOL.md")
    spec = {"panel": f"open_condition_{phase}", "caps": {GOALS: len(jobs), ACTOR: 2 * len(jobs), JUDGE: 2 * len(jobs)},
            "service_reference_sha256": reference, "wire_shas": {uid: sha(wire) for uid, _, wire in jobs},
            "smoke": sorted(smoke), "preflight_evidence": diagnostics, "linked_archive_sha256": digest,
            "comparison_rows_sha256": sha(rows), "judge_cache_sha256": sha(cache[JUDGE]),
            "code_sha256": {p.name: sha(p.read_bytes()) for p in names}, "independent_confirmation": False,
            "thresholds": {"coverage": .90, "max_protected_loss": .02, "max_severity_increase": .05}}
    return spec, jobs, selected, (rows, official, cases), None, cache


def evaluate(inputs, dispatch):
    _, jobs, roots, (rows, official, cases), *_ = inputs
    goal_rows, actors = {}, []
    for (uid, _), (receipt, raw) in dispatch(GOALS, jobs).items():
        state = goal_rows[uid] = {"status": receipt["status"], "request_sha256": receipt["request_sha256"]}
        row, root = rows[uid], roots[uid]
        row["outputs"], row["actor"] = {}, {}
        for arm in method.ARMS:
            row["native"][arm] = {"fields": {}, "status": state["status"]}
        if state["status"] != "OK":
            continue
        try:
            conditions, rejected = method.goals(root["public_task"], root["original_sources"], raw)
        except ValueError:
            state["status"] = "INVALID_GOAL_CONTRACT"
            for arm in method.ARMS:
                row["native"][arm]["status"] = state["status"]
            continue
        state.update(conditions=conditions, rejections=rejected)
        actors.extend((uid, arm, method.actor_request(root["public_task"], root["original_sources"], conditions, arm))
                      for arm in method.ARMS)
    judges = []
    for (uid, arm), (receipt, raw) in dispatch(ACTOR, actors).items():
        row = rows[uid]
        state = row["actor"][arm] = {"status": receipt["status"], "request_sha256": receipt["request_sha256"]}
        if state["status"] == "OK":
            try:
                state["plan"] = method.render(roots[uid]["public_task"], goal_rows[uid]["conditions"], raw)
            except ValueError:
                state["status"] = "INVALID_PLAN_CONTRACT"
            else:
                answer = row["outputs"][arm] = state["plan"]["answer"]
                judges.append((uid, arm, scorer.grade_request(official, cases[uid], answer)))
        row["native"][arm] = {"fields": {}, "status": state["status"]}
    for (uid, arm), (receipt, raw) in dispatch(JUDGE, judges).items():
        rows[uid]["native"][arm] = scorer.parse_grade(receipt, raw, rows[uid]["positions"])
    return goal_rows, list(rows.values())


def summarize(spec, goals, rows, ledger):
    panels = {"all": rows, "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
              "B_only": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
              "has_C": [r for r in rows if "C" in r["labels"]]}
    controls = (method.GENERIC, fusion.ARCHIVED, GATE)
    paired = {panel: {control: {"match": replay.paired(cohort, control, method.OPEN_FIRST),
                                **{f: scorer.comparisons.grade_pair(cohort, control, method.OPEN_FIRST, f)
                                   for f in fusion.active.METRICS}}
                      for control in controls} for panel, cohort in panels.items()}
    counts = {arm: Counter() for arm in method.ARMS}
    for row in rows:
        for arm, actor in row["actor"].items():
            counts[arm][actor["status"]] += 1
            plan = actor.get("plan")
            if plan:
                counts[arm]["has_open_condition"] += bool(plan["required"])
                counts[arm]["open_without_action"] += len(plan["open_without_action"])
                counts[arm]["claimed_supported"] += len(set(plan["required"]) & set(plan["claimed_supported"]))
                counts[arm]["action_linked_verification"] += len(plan["action_linked_verification"])
    return {"assigned": len(rows), "goal_status": Counter(x["status"] for x in goals.values()),
            "actor_contract": counts, "paired": paired,
            "usage": {stage: usage([r for r in ledger if r["unit"]["stage"] == stage]) for stage in spec["caps"]}}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    parser.add_argument("phase", choices=("smoke", "main"))
    args = parser.parse_args()
    action, phase = args.action, args.phase
    out, run = BASE / phase, RUN / phase
    frozen = out / "FROZEN.json"
    reference = probe.read_reference()[1] if action == "freeze" else read(frozen)["service_reference_sha256"]
    inputs = prepare(reference, phase)
    probe.OUT, probe.RUN, replay.OUT = out, run, out
    with (
        probe.runner_lock(run / "runner.lock"),
        patch.object(runtime, "OUT", out),
        patch.object(runtime, "evaluate", evaluate),
        patch.object(runtime, "summarize", summarize),
    ):
        if action == "freeze":
            runtime.manifest(inputs[0]["panel"], GOALS, inputs[1])
            probe.freeze(frozen, inputs[0])
            print(json.dumps(inputs[0]["caps"]))
            return
        state = out / "RUN_STATE.json"
        done = state.exists() and read(state)["state"] == "COMPLETE"
        if action == "run" and not done:
            runtime.execute(inputs, live=True)
        if action == "verify":
            if not done:
                raise ValueError("Comparison has not settled")

            def exact(path, value):
                if read(path) != json.loads(json.dumps(value)):
                    raise ValueError(f"Replay differs in {path.name}")

            with patch.object(probe, "freeze", exact):
                runtime.execute(inputs, live=False)
            print(json.dumps({"verified": True, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
