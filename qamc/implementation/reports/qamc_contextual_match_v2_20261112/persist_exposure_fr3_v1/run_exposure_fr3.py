"""Run matched exposure and retain unchanged historical samples by repeat."""
import argparse
from collections import Counter, defaultdict
from itertools import product
import json
from pathlib import Path

from check_exposure_fr3 import POLICIES, group_endpoint, inspect_prior, judge_wire, prepare
from complete import RUN as OLD_RUN, actor_request, engine, probe, read, select
from qamc.common import sha
from repeat_receipts import branch, plan_receipts
from transfer_replay import persist

HERE = Path(__file__).resolve().parent
RUN = OLD_RUN.with_name(HERE.name)
ROLES = ("Route", "Select", "Actor", "Judge")
BU = "beneficial_memory_usage"


def repetitions(case):
    return 1 if case["category"] == BU else 3


def appointment(cases):
    # Settle the already matched 19 risk roots first, with no changes to the
    # 49-root allocation or to the remaining roots and control arms.
    earlier = read(OLD_RUN.parent / "persist_equal_cap_safety_v1" / "FROZEN.json")["tracks"]
    for group, roots in (("Matched", set(earlier)), ("Remaining", set(cases) - earlier.keys())):
        for repeat in (1, 2, 3):
            eligible = [uid for uid in sorted(roots) if repeat <= repetitions(cases[uid])]
            if eligible:
                yield group + str(repeat), repeat, eligible


def make_cell(arm, row, judge, track, failure=None):
    score = None
    if judge and judge["status"] == "OK":
        scorer = persist.author.ext.parent.persist
        try:
            score = scorer.score(track, judge["answer"])
        except (ValueError, TypeError, KeyError):
            failure = "INVALID_SCORE"
    return {
        "arm": arm, "actor": row, "judge": judge, "score": score,
        "status": failure or (judge or row or {"status": "UNISSUED"})["status"],
    }


def resolve(label, repeat, uids, cases, inputs, protocol, build_grade, saved, dispatch):
    def stage(role, jobs):
        resolved, fresh = {}, {}
        for (uid, arm), wire in jobs.items():
            cached = saved.get((uid, repeat), {}).get((role, sha(wire)))
            if cached is not None:
                resolved[uid, arm] = cached
            else:
                fresh[uid, arm] = wire
        resolved.update(dispatch(label + role, fresh))
        return resolved

    routing = {(uid, "SELECTED"): inputs[uid]["selection_requests"]["query"] for uid in uids}
    routes = stage("Route", routing)
    selections, faults, branches = {}, {}, {}
    for (uid, arm), result in routes.items():
        if result["status"] != "OK":
            faults[uid] = result["status"]
            continue
        task = inputs[uid]["public"]
        try:
            branches[uid] = branch(task, result["answer"])
            selections[uid, arm] = inputs[uid]["selection_requests"][branches[uid]]
        except (KeyError, TypeError, ValueError):
            faults[uid] = "INVALID_ROUTE"
    answers = {(uid, arm): inputs[uid][arm] for uid in uids
               for arm in ("FULL", "EMPTY", "RUBRIC")}
    exposure, grouped = {}, {}
    selection_receipts = stage("Select", selections)
    for (uid, arm), result in selection_receipts.items():
        if result["status"] != "OK":
            faults[uid] = result["status"]
            continue
        task = inputs[uid]["public"]
        try:
            sources = select(cases[uid], task, routes[uid, arm]["answer"], result["answer"])
            endpoint = group_endpoint(sources, task["memories"])
            answers[uid, arm] = actor_request(cases[uid], task["query"], sources,
                                             protocol, protocol["prompts"]["gepa"])
            grouped[uid] = endpoint
            exposure[uid] = {
                "branch": branches[uid], "count": len(sources), "sha256": sha(sources),
                "group_endpoint": endpoint,
                "selected_equals_group": answers[uid, arm] == answers[uid, endpoint],
            }
        except (KeyError, TypeError, ValueError):
            faults[uid] = "INVALID_SELECTION"
    generated = stage("Actor", answers)
    graders = {(uid, arm): build_grade(uid, reply["answer"])
               for (uid, arm), reply in generated.items() if reply["status"] == "OK"}
    grades = stage("Judge", graders)
    rows = []
    for uid in uids:
        track = cases[uid]["category"]
        methods = {}
        for arm in POLICIES:
            endpoint = grouped.get(uid) if arm == "GROUP" else arm
            key = uid, endpoint
            failure = faults.get(uid) if arm in ("SELECTED", "GROUP") else None
            methods[arm] = make_cell(arm, generated.get(key), grades.get(key), track, failure)
        rows.append({
            "uid": uid, "repeat": repeat, "track": track, "methods": methods,
            "exposure": exposure.get(uid), "route": routes.get((uid, "SELECTED")),
            "selector": selection_receipts.get((uid, "SELECTED")),
        })
    return rows


def risk(cell, track):
    key = "failure_strict_utility" if track == BU else "failure_release"
    return int(cell["score"][key]) if cell and cell["score"] is not None else None


def same_result_position(left, right):
    if not left or not right:
        return False
    for stage in ("actor", "judge"):
        a, b = left[stage], right[stage]
        if a and b and a["request_sha256"] == b["request_sha256"]:
            return True
    return False


def possible(left, right, track):
    a, b = risk(left, track), risk(right, track)
    if same_result_position(left, right):
        if a != b:
            raise ValueError("Shared repeat endpoint has divergent outcomes")
        return [(0, 0), (1, 1)] if a is None else [(a, a)]
    return list(product((0, 1) if a is None else (a,), (0, 1) if b is None else (b,)))


def compare(grid, count, track, left, right):
    results, bounds = Counter(), [0, 0]
    for rows in grid:
        series = [[(r["methods"].get(arm) if r else None) for r in rows[:count]] for arm in (left, right)]
        observed = [[risk(cell, track) for cell in column] for column in series]
        states = ["failure" if 1 in vals else "unknown" if None in vals else "pass" for vals in observed]
        results["left_" + states[0]] += 1
        results["right_" + states[1]] += 1
        if "unknown" in states:
            results["pair_unknown"] += 1
        else:
            results["tie" if states[0] == states[1] else "win" if states[0] == "pass" else "loss"] += 1
        options = [possible(a, b, track) for a, b in zip(*series, strict=True)]
        net = [max(a for a, _ in terms) - max(b for _, b in terms) for terms in product(*options)]
        bounds[0] += min(net)
        bounds[1] += max(net)
    return {"counts": results, "failure_difference_bounds": bounds}


def summarize(cases, rows, ledger):
    observed = {(row["uid"], row["repeat"]): row for row in rows}
    tracks = defaultdict(list)
    for uid, case in cases.items():
        tracks[case["category"]].append([observed.get((uid, repeat))
                                        for repeat in range(1, repetitions(case) + 1)])
    comparisons = (("SELECTED", "GROUP"), ("GROUP", "EMPTY"), ("GROUP", "FULL"),
                   ("FULL", "RUBRIC"), ("SELECTED", "RUBRIC"))
    result = {}
    for track, grids in tracks.items():
        result[track] = {str(count): {f"{left}_vs_{right}": compare(grids, count, track, left, right)
                                    for left, right in comparisons}
                         for count in range(1, len(grids[0]) + 1)}
    return {
        "cases": len(cases), "settled_repeat_positions": len(observed),
        "outcomes": result,
        "status_by_policy": {arm: Counter(row["methods"][arm]["status"] for row in rows)
                             for arm in POLICIES},
        "new_dispatches": {
            "physical": len(ledger), "status": Counter(r["status"] for r in ledger),
            "usage_unknown": sum("total_tokens" not in (r.get("usage") or {}) for r in ledger),
            "reported_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in ledger),
        },
    }


def registration(cases, saved):
    groups = list(appointment(cases))
    pins, costs = [], {}
    for label, repeat, uids in groups:
        reused = [r for uid in uids for r in saved.get((uid, repeat), {}).values()]
        counts = Counter(role for uid in uids for role, _ in saved.get((uid, repeat), {}))
        costs[label] = {
            "positions": len(uids), "archived_requests": sum(counts.values()),
            "archived_by_stage": counts,
            "old_unsuccessful_attempts": sum(r["status"] != "OK" for r in reused),
        }
        pins.append([label, repeat, uids])
    summary = {
        "positions_per_arm": sum(v["positions"] for v in costs.values()),
        "new_request_upper_bound": sum(v["positions"] * 10 - v["archived_requests"]
                                       for v in costs.values()),
        "stages": costs,
    }
    return sha(pins), summary


def verify(cases, inputs, protocol, judge, bounds, saved):
    """Replay all logical positions with missing fresh requests and no transport."""
    build_grade = judge_wire(cases, inputs, judge, bounds)
    allocations, rows = {}, []
    for label, repeat, uids in appointment(cases):
        needed = Counter()

        def undispatched(stage, fresh):
            if fresh:
                needed[stage.removeprefix(label)] += len({sha(wire) for wire in fresh.values()})
            return {key: {"status": "UNISSUED", "answer": None, "request_sha256": sha(wire)}
                    for key, wire in fresh.items()}

        rows.extend(resolve(label, repeat, uids, cases, inputs, protocol, build_grade, saved, undispatched))
        allocations[label] = needed
    result = summarize(cases, rows, [])
    assert result["settled_repeat_positions"] == 111
    assert sum(r["exposure"] is None for r in rows) > 0
    assert allocations["Matched1"] == {"Actor": 19} == allocations["Matched2"], allocations
    assert not any("Route" in allocations[f"Matched{wave}"] for wave in (1, 2, 3))

    held = [r for r in rows if r["repeat"] == 3
            and r["methods"]["SELECTED"]["status"] == "FAILED_DELIVERY_UNKNOWN"]
    assert len(held) == 1
    held_arms = held[0]["methods"]
    assert held_arms["SELECTED"]["actor"] == held_arms["GROUP"]["actor"] == held_arms["EMPTY"]["actor"]
    assert not any(held_arms[arm]["judge"] for arm in ("SELECTED", "GROUP", "EMPTY"))
    return {"initial_dispatches_after_cache": allocations,
            "new_model_requests": 0, "old_shared_unknown_preserved": len(held)}


def execute(identity, cases, inputs, protocol, judge, bounds, saved):
    RUN.mkdir(parents=True, exist_ok=True)
    engine.RUN = engine.OUT = probe.RUN = probe.OUT = RUN
    engine.CAP = {}
    history = []
    ledger = []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)
        for label, repeat, uids in appointment(cases):
            path = RUN / (label + "_SETTLED.json")
            if path.exists():
                payload = read(path)
                if payload["identity"] != identity:
                    raise ValueError("Checkpoint belongs to another plan")
            else:
                this_ledger = []

                def dispatch(stage, fresh):
                    if not fresh:
                        return {}
                    engine.CAP[stage] = 4 * len(uids) if stage.endswith(("Actor", "Judge")) else len(uids)
                    return engine.stage(stage, fresh, identity, True, this_ledger)

                answer_grid = resolve(label, repeat, uids, cases, inputs, protocol,
                                      judge_wire(cases, inputs, judge, bounds), saved, dispatch)
                payload = {"identity": identity, "rows": answer_grid, "ledger": this_ledger}
                probe.freeze(path, payload)
            history.extend(payload["rows"])
            ledger.extend(payload["ledger"])
            print(json.dumps({"settled_batch": label, "completed_repeat_positions": len(history),
                              "new_physical_requests": len(ledger)}), flush=True)
        probe.freeze(RUN / "RESULTS.json", {"rows": history, "ledger": ledger})
        probe.freeze(RUN / "RESULTS_SUMMARY.json", summarize(cases, history, ledger))


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("action", choices=("freeze", "verify", "run"))
    action = arg.parse_args().action
    cases, inputs, protocol, judge, bounds = prepared = prepare()
    audit = inspect_prior(prepared)
    signature = read(OLD_RUN.parent / "persist_equal_cap_safety_v1" / "EXECUTION.json")["service_reference_sha256"]
    saved = plan_receipts(*prepared, signature)
    roster_hash, counts = registration(cases, saved)
    lock = {
        "schedule_sha256": roster_hash, "preflight_sha256": sha(audit),
        "archive_sha256": sha([[list(key), [[list(cell), item["ref"], item["status"],
                                            sha(item["answer"])] for cell, item in cells.items()]]
                                for key, cells in sorted(saved.items())]),
        "code": {name: sha((HERE / name).read_text()) for name in (
            "execute.sh", "run_exposure_fr3.py", "repeat_receipts.py", "check_exposure_fr3.py", "PROTOCOL.md",
        )},
        "registration": counts,
    }
    if action == "freeze":
        RUN.mkdir(parents=True, exist_ok=True)
        probe.freeze(RUN / "REGISTERED.json", lock)
        print(json.dumps(counts, sort_keys=True, indent=2))
    elif action == "verify":
        print(json.dumps(verify(*prepared, saved), sort_keys=True, indent=2))
    else:
        if read(RUN / "REGISTERED.json") != lock:
            raise ValueError("Request roster or compatible receipts changed")
        if probe.read_reference()[1] != signature:
            raise ValueError("New gateway configuration does not match archived repeats")
        execute({"experiment_sha256": sha(lock), "service_reference_sha256": signature},
                cases, inputs, protocol, judge, bounds, saved)


if __name__ == "__main__":
    main()
