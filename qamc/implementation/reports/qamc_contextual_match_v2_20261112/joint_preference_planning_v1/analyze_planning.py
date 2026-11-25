"""Read-only audit of the joint planning intervention and its native answer scores."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import planning
import run_joint_planning as run


def domains_for(plan):
    return {
        f"D{i}": {f"O{j}": option for j, option in enumerate(decision["options"], 1)}
        for i, decision in enumerate(plan["decisions"], 1)
    }


def intervention(trace):
    """Diagnose what changes the choice, under the same model-built domains."""
    if "solver" not in trace:
        return None
    model = trace["selections"][run.MODEL]
    chosen = trace["selections"][run.SOLVED]
    plan = trace["plan"]
    if chosen == model:
        return {"effect": "UNCHANGED", "changed_slots": [], "axes": []}
    if chosen is None:
        return {"effect": "NO_JOINT_SOLUTION", "changed_slots": [], "axes": []}
    domains = domains_for(plan)
    hard, soft = plan["hard"], plan["soft"]
    without_joint = planning.solve(domains, [row for row in hard if len(row["choices"]) == 1], soft, model)
    without_soft = planning.solve(domains, hard, [], model)
    axes = []
    if without_joint["selection"] != chosen:
        axes.append("MULTI_DECISION_HARD_CLAUSE")
    if without_soft["selection"] != chosen:
        axes.append("SOFT_PREFERENCE")
    if trace["solver"]["control_conflicts"]:
        axes.append("MODEL_HARD_CONFLICT")
    effect = "JOINT_HARD" if "MULTI_DECISION_HARD_CLAUSE" in axes else (
        "OTHER_HARD" if "MODEL_HARD_CONFLICT" in axes else "RANKING"
    )
    ranking = zip(("TASK_COST", "UNVERIFIED_PRECONDITIONS", "SOFT_SUPPORT", "MODEL_DEVIATION"),
                  trace["solver"]["control_rank"], trace["solver"]["solved_rank"], strict=True)
    rank_driver = next((name for name, before, after in ranking if before != after), None)
    return {"effect": effect, "changed_slots": [slot for slot in model if model[slot] != chosen[slot]],
            "axes": axes, "rank_driver": rank_driver if effect == "RANKING" else None}


def planning_receipts(frozen, actor_wires=None):
    """Replay persisted planning receipts without allocating work or reading judge labels."""
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    manifest = run.read(run.OUT / f"{run.PLAN}_MANIFEST.json")
    requests = {sha(job["request"]): job for job in manifest["units"]}
    assignments = frozen["planner_wires_sha256"]
    if requests.keys() != set(assignments.values()):
        raise ValueError("Planner manifest differs from the frozen task roster")
    receipts = run.probe.stage_receipts(run.PLAN)
    traces = {}
    for uid, digest in assignments.items():
        job = requests[digest]
        record, raw = receipts[job["unit"]["root_id"], job["unit"]["method"]]
        if record is None:
            traces[uid] = {"status": "UNISSUED"}
            continue
        if record["request_sha256"] != digest:
            raise ValueError("Planner receipt belongs to a different request")
        payload = json.loads(job["request"]["messages"][1]["content"])
        compiled, jobs = run.construct_actor_jobs(
            {uid: payload}, {(uid, "SHARED_PLAN"): (record, raw)}, {uid: digest}
        )
        traces[uid] = compiled[uid]
        if actor_wires is not None:
            actor_wires.update({(task, method): wire for task, method, wire in jobs})
    return traces, receipts


def actor_wire_audit(traces, wires, manifest=None):
    """Prove both Actor inputs are identical after removing the selected combination."""
    checked, changed, hashes = 0, 0, set()
    for uid, trace in traces.items():
        arms = [wires.get((uid, method)) for method in planning.METHODS]
        if not any(arms):
            continue
        if not all(arms):
            raise ValueError("Only one arm received an Actor request")
        if any([m["role"] for m in wire["messages"]] != ["system", "user"] for wire in arms):
            raise ValueError("Unexpected roles or extra Actor messages")
        left, right = [json.loads(wire["messages"][1]["content"]) for wire in arms]
        selected = [left.pop("selection"), right.pop("selection")]
        if selected != [trace["selections"][method] for method in planning.METHODS]:
            raise ValueError("Actor request differs from the compiled decision")
        if left.keys() != {"task", "source_evidence", "plan"} or left["plan"] != trace["plan"]:
            raise ValueError("Actor does not receive the common plan and expected fields")
        metadata = [{k: v for k, v in wire.items() if k != "messages"} for wire in arms]
        if left != right or metadata[0] != metadata[1]:
            raise ValueError("The Actor arms differ outside the compiled selection")
        if any(wire["messages"][1]["content"] != json.dumps({**left, "selection": value}, ensure_ascii=False)
               for wire, value in zip(arms, selected, strict=True)):
            raise ValueError("Actor input serialization differs outside the compiled selection")
        if arms[0]["messages"][:1] != arms[1]["messages"][:1]:
            raise ValueError("The Actor arms use different system prompts")
        pair = [sha(wire) for wire in arms]
        if (selected[0] == selected[1]) != (pair[0] == pair[1]):
            raise ValueError("Identical selections do not share the same Actor wire")
        hashes.update(pair)
        changed += pair[0] != pair[1]
        checked += 1
    result = {"paired_requests_checked": checked, "changed_selection_requests": changed,
              "unique_actor_wires_in_snapshot": len(hashes), "actual_actor_manifest_verified": False}
    if manifest is not None:
        rows = manifest["units"]
        frozen = {(row["unit"]["root_id"], row["unit"]["method"]): row["request"] for row in rows}
        if (len(rows) != len(hashes) or len(rows) != len(frozen)
                or {sha(wire) for wire in frozen.values()} != hashes
                or any(wires.get(key) != wire for key, wire in frozen.items())):
            raise ValueError("The allocated Actor manifest disagrees with the audited requests")
        result["actual_actor_manifest_verified"] = True
    return result


def plan_summary(traces):
    effects, axes, errors, statuses = Counter(), Counter(), Counter(), Counter()
    ranking_drivers = Counter()
    real_joint_clauses, hard_links, soft_links = 0, 0, 0
    for trace in traces.values():
        statuses[trace["status"]] += 1
        if "error" in trace:
            errors[trace["error"]] += 1
        effect = intervention(trace)
        if effect is None:
            continue
        effects[effect["effect"]] += 1
        axes.update(effect["axes"])
        if effect.get("rank_driver"):
            ranking_drivers[effect["rank_driver"]] += 1
        hard_links += len(trace["plan"]["hard"])
        soft_links += len(trace["plan"]["soft"])
        real_joint_clauses += sum(len(row["choices"]) > 1 for row in trace["plan"]["hard"])
    return {"logical_status": statuses, "plan_effect": effects, "effect_axes_overlap": axes,
            "first_changed_ranking_term": ranking_drivers,
            "hard_clauses": hard_links, "soft_clauses": soft_links,
            "multi_decision_hard_clauses": real_joint_clauses, "parse_errors": errors}


def answer_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        status = intervention(row["planning"])
        if status is not None:
            groups[status["effect"]].append(row)
    summary = {}
    for effect, sample in sorted(groups.items()):
        match = run.v42.paired(sample, run.MODEL, run.SOLVED)
        a, b = run.MODEL, run.SOLVED
        changed = sum(bool(row["actors"][a].get("answer")) and bool(row["actors"][b].get("answer"))
                      and row["actors"][a]["answer"] != row["actors"][b]["answer"] for row in sample)
        summary[effect] = {
            "assigned": len(sample), "source_groups": len({row["group"] for row in sample}),
            "changed_answers": changed, "match": match,
            **{field: run.parent.comparisons.grade_pair(sample, a, b, field) for field in run.SUPPORT},
        }
    return summary


def seed_comparison(joint_rows):
    from run_seed_control import OUT as control, edit

    state = control / "RUN_STATE.json"
    if not state.exists() or run.read(state)["state"] != "COMPLETE":
        return None
    threshold = run.read(control / "FROZEN.json")["review_screen_match_gain"]
    seed_rows = run.read(control / "SETTLED.json")["rows"]
    rows = []
    for joint_row, seed in zip(joint_rows, seed_rows, strict=True):
        keys = ("uid", "group", "labels", "positions")
        if any(joint_row[k] != seed[k] for k in keys):
            raise ValueError("The RP revision and planning results differ in task identity or grading scope")
        rows.append({**joint_row, "native": {**joint_row["native"], edit.METHOD: seed["native"][edit.METHOD]}})
    panels = {
        "all": rows,
        "all_A": [r for r in rows if set(r["labels"]) == {"A"}],
        "contains_BC": [r for r in rows if "B" in r["labels"] or "C" in r["labels"]],
        "contains_C": [r for r in rows if "C" in r["labels"]],
        "B_without_C": [r for r in rows if "B" in r["labels"] and "C" not in r["labels"]],
    }
    metrics = {name: {
        "match": run.v42.paired(sample, edit.METHOD, run.SOLVED),
        **{f: run.parent.comparisons.grade_pair(sample, edit.METHOD, run.SOLVED, f) for f in run.SUPPORT},
    } for name, sample in panels.items()}
    main = metrics["all"]["match"]
    metrics["review_match_screen"] = {
        "minimum_gain": threshold,
        "observed_gain": main.get("match_delta"),
        "positive_lower_bound": main.get("95pct_source_bootstrap", [-1])[0] > 0,
        "cleared_gain_and_interval": (main.get("match_delta", -1) >= threshold
                                      and main.get("95pct_source_bootstrap", [-1])[0] > 0),
    }
    return metrics


def audit():
    frozen = run.read(run.OUT / "FROZEN.json")
    state = run.read(run.OUT / "RUN_STATE.json")
    actor_manifest = run.OUT / f"{run.ACTOR}_MANIFEST.json"
    actual = run.read(actor_manifest) if actor_manifest.exists() else None
    wires = {}
    traces, receipts = planning_receipts(frozen, wires)
    result = {
        "run_state_at_read": state["state"], "assigned": len(traces),
        "planner_physical_status": Counter(record["status"] for record, _ in receipts.values() if record),
        **plan_summary(traces),
        "actor_request_fairness": actor_wire_audit(traces, wires, actual),
    }
    if state["state"] == "COMPLETE":
        settled = run.read(run.OUT / "SETTLED.json")
        if {(row["uid"], row["planning"]["status"]) for row in settled["rows"]} != {
            (uid, row["status"]) for uid, row in traces.items()
        } or len(settled["rows"]) != len(traces):
            raise ValueError("Settled results do not cover the frozen planner diagnostics")
        result["answer_outcomes_by_observed_intervention"] = answer_summary(settled["rows"])
        comparable = seed_comparison(settled["rows"])
        if comparable is not None:
            result["against_rp_seed_minimal_revision"] = comparable
    return result


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
