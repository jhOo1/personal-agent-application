"""Repeat frozen PersistBench deployments using the existing request journal."""
import argparse
from collections import Counter
import json
from pathlib import Path

from complete import AUTHOR, BASE, engine, get_author, normalized, passes, probe, read
from compare_controls import load_verified_scores
from persist_grounding_gepa_wires import actor_request, input_requests, select, transfer
from qamc.common import sha
from transfer_replay import persist

HERE = Path(__file__).resolve().parent
RUN = engine.RUN.with_name(HERE.name)
ACTIVE = "SELECTED_GEPA"
CONTROLS = ("PB_RUBRIC", "PB_GEPA")
METHODS = (ACTIVE, *CONTROLS)
TRACKS = {"sycophancy": (None, 3), "cross_domain": (8, 3), "beneficial_memory_usage": (6, 1)}


def prepare():
    selected, controls = load_verified_scores()
    author, bounds, _ = get_author()
    plan = read(AUTHOR.parent / "PLAN.json")
    archived = {(r["uid"], r["method"]): r for r in author}
    cases = {}
    for track, (limit, _) in TRACKS.items():
        eligible = [r for r in plan["cases"] if r["role"] == "DEV" and r["category"] == track
                    and r["uid"] in selected and all(m in controls[r["uid"]] for m in CONTROLS)]
        groups = set()
        for case in sorted(eligible, key=lambda r: sha(["pb-repeated-deployment-v1", r["uid"]])):
            if case["group_id"] in groups:
                continue
            groups.add(case["group_id"])
            cases[case["uid"]] = case
            if len(groups) == limit:
                break
        if not groups:
            raise ValueError(f"No eligible cases for {track}")
    factorial = read(transfer.ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    route_protocol = read(transfer.OUT / "PLAN.json")
    data = {}
    for uid, case in cases.items():
        task = persist.author.parent.smoke.task_for(case)
        public = {"query": task.query, "memories": [m.text for m in task.memories]}
        if sha(public) != case["public_sha256"]:
            raise ValueError("Frozen inputs changed")
        full = {}
        for method in CONTROLS:
            old = archived[uid, method]
            wire = old["actor_request"]
            if sha(wire) != old["actor_request_sha256"]:
                raise ValueError("Archived Actor request changed")
            full[method] = wire
        data[uid] = (public, input_requests(case, public, route_protocol), full)
    pin = {"split": "exposed_dev", "cases": {uid: r["category"] for uid, r in cases.items()},
           "inputs": sha(data), "judge_envelopes": sha({uid: bounds[uid] for uid in cases}),
           "actor_protocol": sha([factorial["protocols"], factorial["prompts"]["gepa"]]),
           "source_groups": sha({uid: r["group_id"] for uid, r in cases.items()}),
           "code": sha(Path(__file__).read_bytes()), "protocol": sha((HERE / "PROTOCOL.md").read_bytes()),
           "cap": 8 * sum(TRACKS[r["category"]][1] for r in cases.values())}
    return pin, cases, data, factorial, plan["protocols"]["gpt41"], bounds


def wave(number, cases, data, factorial, judge_proto, bounds, identity, ledger):
    panel = {uid: r for uid, r in cases.items() if number <= TRACKS[r["category"]][1]}
    scorer = persist.author.ext.parent.persist
    _, rubrics, formatter = scorer.upstream()

    def dispatch(label, jobs):
        if not jobs:
            return {}
        stage = f"Draw{number}_{label}"
        engine.CAP[stage] = len(panel) * (len(METHODS) if label == "Judge" else 1)
        return engine.stage(stage, jobs, identity, True, ledger)

    routes = dispatch("Route", {(uid, ACTIVE): data[uid][1]["query"] for uid in panel})
    selector_wires, branches, failures = {}, {}, {}
    for (uid, method), reply in routes.items():
        if reply["status"] != "OK":
            failures[uid] = reply["status"]
            continue
        try:
            route = transfer.confirmation.route.decode(reply["answer"], data[uid][0]["query"])
            branch = "style" if route["check_history"] else "grounding"
            branches[uid] = branch
            selector_wires[uid, method] = data[uid][1][branch]
        except (ValueError, TypeError, KeyError):
            failures[uid] = "INVALID_ROUTE"
    selectors = dispatch("Select", selector_wires)
    selected_wires, selected_counts, selected_hashes = {}, {}, {}
    for (uid, method), reply in selectors.items():
        if reply["status"] != "OK":
            failures[uid] = reply["status"]
            continue
        try:
            case, public = panel[uid], data[uid][0]
            evidence = select(case, public, routes[uid, method]["answer"], reply["answer"])
            selected_wires[uid, method] = actor_request(
                case, public["query"], evidence, factorial, factorial["prompts"]["gepa"])
            selected_counts[uid], selected_hashes[uid] = len(evidence), sha(evidence)
        except (ValueError, TypeError, KeyError):
            failures[uid] = "INVALID_SELECTION"
    answers = dispatch("SelectedActor", selected_wires)
    for method in CONTROLS:
        answers.update(dispatch(method, {(uid, method): data[uid][2][method] for uid in panel}))

    judges = {}
    for (uid, method), reply in answers.items():
        if reply["status"] == "OK":
            public, track = data[uid][0], panel[uid]["category"]
            wire = persist.author.ext.text_request(
                rubrics[track], formatter["build_judge_prompt"](
                    public["memories"], public["query"], reply["answer"]),
                judge_proto["model"], judge_proto["stages"][persist.STAGE]["max_tokens"])
            if normalized(wire, reply["answer"]) != bounds[uid]:
                raise ValueError("Judge envelope drift")
            judges[uid, method] = wire
    scores = dispatch("Judge", judges)

    rows = []
    for uid, case in panel.items():
        for method in METHODS:
            actor = answers.get((uid, method), {})
            judge = scores.get((uid, method), {})
            score = None
            status = judge.get("status", actor.get("status", failures.get(uid, "UNISSUED")))
            if judge.get("status") == "OK":
                try:
                    score = scorer.score(case["category"], judge["answer"])
                except (ValueError, TypeError, KeyError):
                    status = "INVALID_SCORE"
            rows.append({"uid": uid, "draw": number, "method": method, "category": case["category"],
                         "status": status, "answer": actor.get("answer"), "judge": judge, "score": score,
                         "branch": branches.get(uid) if method == ACTIVE else None,
                         "selected_count": selected_counts.get(uid) if method == ACTIVE else None,
                         "selected_sha256": selected_hashes.get(uid) if method == ACTIVE else None})
    return rows


def run(pin, cases, data, factorial, judge_proto, bounds):
    if pin != read(RUN / "FROZEN.json"):
        raise ValueError("Frozen plan drift")
    engine.OUT = probe.OUT = probe.RUN = RUN
    identity = {"experiment_sha256": sha(pin), "service_reference_sha256": probe.read_reference()[1]}
    ledger, rows = [], []
    with probe.runner_lock(RUN / "runner.lock"):
        probe.freeze(RUN / "EXECUTION.json", identity)
        for number in range(1, 4):
            checkpoint = RUN / f"DRAW{number}.json"
            if checkpoint.exists():
                result = read(checkpoint)
                if result["identity"] != identity:
                    raise ValueError("Checkpoint identity drift")
                rows.extend(result["rows"])
                ledger.extend(result["ledger"])
                continue
            calls = []
            batch = wave(number, cases, data, factorial, judge_proto, bounds, identity, calls)
            rows.extend(batch)
            ledger.extend(calls)
            if len(ledger) > pin["cap"]:
                raise ValueError("Run exceeded planned capacity")
            probe.freeze(checkpoint, {"identity": identity, "rows": batch, "ledger": calls})
        probe.freeze(RUN / "RESULTS.json", {"rows": rows, "ledger": ledger})


def task_outcome(draws):
    if False in draws:
        return "FAIL"
    if None in draws:
        return "UNKNOWN"
    return "PASS"


def summary():
    result = read(RUN / "RESULTS.json")
    pin = read(RUN / "FROZEN.json")
    by = {(r["uid"], r["method"], r["draw"]): r for r in result["rows"]}
    if len(by) != len(result["rows"]):
        raise ValueError("Duplicate result")
    comparisons, methods, stability = {}, {}, {}
    for track, (_, draws) in TRACKS.items():
        outcomes = {}
        for uid, category in pin["cases"].items():
            if category != track:
                continue
            active = [by[uid, ACTIVE, i] for i in range(1, draws + 1)]
            if draws > 1 and all(r["selected_sha256"] for r in active):
                key = "constant_evidence" if len({r["selected_sha256"] for r in active}) == 1 else "changed_evidence"
                stability.setdefault(track, Counter())[key] += 1
            for method in METHODS:
                values = [(passes(r["score"], track) if r["score"] is not None else None)
                          for r in (by[uid, method, i] for i in range(1, draws + 1))]
                outcomes[uid, method] = task_outcome(values)
                totals = methods.setdefault(f"{track}/{method}", Counter())
                totals[outcomes[uid, method]] += 1
                totals.update({"draw_fail": values.count(False), "draw_valid": draws - values.count(None),
                               "draw_assigned": draws})
        for method in CONTROLS:
            totals = comparisons[f"{track}/{method}"] = Counter()
            for uid, category in pin["cases"].items():
                if category != track:
                    continue
                left, right = outcomes[uid, ACTIVE], outcomes[uid, method]
                totals.update({f"{left}/{right}": 1})
    ledger = result["ledger"]
    return {"methods": methods, "paired": comparisons, "evidence_stability": stability,
            "row_statuses": Counter(r["status"] for r in by.values()),
            "requests": len(ledger), "request_statuses": Counter(r["status"] for r in ledger),
            "reported_tokens": sum((r["usage"] or {}).get("total_tokens", 0) for r in ledger),
            "unknown_usage": sum("total_tokens" not in (r["usage"] or {}) for r in ledger)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "summary"))
    action = parser.parse_args().action
    if action == "summary":
        print(json.dumps(summary(), indent=2, sort_keys=True))
    else:
        inputs = prepare()
        if action == "freeze":
            probe.freeze(RUN / "FROZEN.json", inputs[0])
        else:
            run(*inputs)
        print(json.dumps({"cohort": Counter(inputs[0]["cases"].values()),
                          "hash": sha(inputs[0]), "max_requests": inputs[0]["cap"]}))
