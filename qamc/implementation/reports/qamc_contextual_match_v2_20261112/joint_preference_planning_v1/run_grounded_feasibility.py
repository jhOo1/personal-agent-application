"""Run evidence-sensitive choice compilation on matched exposed hard-condition histories."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import grounded_feasibility as method
import run_beneficiary_ranking as prior
from settle_joint_planning import score_matrix, usage


OUT = prior.OUT.with_name("grounded_feasibility_rpeval_v1")
RUN = prior.RUN.with_name(OUT.name)
TASK, POLICY, JUDGE = prior.TASK, "FeasibilityDecision", prior.JUDGE
SHARED, probe, read, replay = prior.SHARED, prior.probe, prior.read, prior.replay
KNOWN = ("explicit/008", "explicit/048", "explicit/054", "explicit/144",
         "implicit/037", "implicit/100", "implicit/116", "implicit/133")
BASELINES = (prior.parent.GATE, prior.parent.RP)
ARMS = (*method.MODES, *BASELINES)
CONDITIONS = ("guard", "comparison")


def prepare():
    old_spec, _, roots, rows, _, archive = prior.parent.prior.prepare("pilot")
    realization = prior.parent.prior.parent.parent.parent.OUT / "SETTLED.json"
    predictions = {row["uid"]: row["selection"] for row in read(realization)["rows"]}
    source = {row["uid"]: row for row in rows}
    families = defaultdict(lambda: defaultdict(list))
    excluded = set(old_spec["diagnostic_source_groups"])
    observed = {}
    for uid, root in roots.items():
        record, key = predictions[uid], root["task_wire_sha256"]
        if record["status"] != "OK":
            continue
        group = source[uid]["group"]
        condition = "guard" if any(x["use"] == "GUARD" for x in record["uses"]) else "comparison"
        families[group, key][condition].append(uid)
        if uid.endswith(KNOWN):
            excluded.add(group)
            observed[group, key] = (condition, uid)
    panels, selected_groups = [], set()
    for group, key in sorted(families, key=lambda x: sha(["grounded-feasibility-v1", x])):
        choices = families[group, key]
        if len(choices) != 2 or group in selected_groups:
            continue
        primary = group not in excluded
        if not primary and (group, key) not in observed:
            continue
        selected = {k: min(choices[k], key=lambda uid: sha(["feasibility-history", uid])) for k in CONDITIONS}
        if not primary:
            condition, uid = observed[group, key]
            selected[condition] = uid
        a, b = (roots[selected[k]] for k in CONDITIONS)
        if (a["public_task"] != b["public_task"]
                or sha(a["original_sources"]) == sha(b["original_sources"])):
            raise ValueError("Counterpart task or historical evidence differs from design")
        panels.append({"task": key, "group": group, "primary": primary, **selected})
        selected_groups.add(group)
    primary_count = sum(p["primary"] for p in panels)
    if primary_count != 22:
        raise ValueError("Unexpected primary source group coverage")
    wires = {p["guard"]: method.rank.task_request(roots[p["guard"]]) for p in panels}
    reuse = read(prior.OUT / f"{TASK}_EXACT.json")
    reused_count = sum(sha(wire) in reuse for wire in wires.values())
    base = Path(__file__).resolve().parents[3]
    files = (Path(__file__), Path(method.__file__), Path(method.rank.__file__),
             Path(method.rank.draft.__file__), Path(method.rank.grounded.__code__.co_filename),
             Path(method.rank.planning.__file__), Path(replay.__file__), Path(replay.prior.__file__),
             Path(__file__).with_name("GROUNDED_FEASIBILITY_PROTOCOL.md"), realization,
             prior.OUT / f"{TASK}_EXACT.json", prior.parent.prior.parent.OUT / "SETTLED.json",
             prior.parent.prior.BASE_OUT / "pilot/FROZEN.json",
             prior.parent.prior.parent.joint.prior.OUT / "FROZEN.json",
             prior.parent.prior.parent.joint.prior.formal.OUT / "PLAN.json")
    spec = {"pairs": panels, "source_groups": primary_count,
            "caps": {TASK: len(wires) - reused_count, POLICY: 2 * len(wires), JUDGE: 8 * len(wires)},
            "service_reference_sha256": old_spec["service_reference_sha256"],
            "inputs_sha256": {str(p.resolve().relative_to(base)): sha(p.read_bytes()) for p in files},
            "shared_task_requests": {uid: sha(wire) for uid, wire in wires.items()},
            "task_cache_hits": reused_count,
            "screen": {"valid_fraction": .90, "min_fm_improvement": .10, "protect_match": -.02,
                       "protect_bias": .05},
            "independent_confirmation": False}
    return spec, wires, source, roots, archive


def generate(inputs, stage):
    spec, wires, data, roots, _ = inputs
    samples = stage(TASK, [(uid, SHARED, wire) for uid, wire in wires.items()])
    rows, pending = {}, []
    for pair in spec["pairs"]:
        first = pair["guard"]
        receipt, raw = samples[first, SHARED]
        state = receipt["status"]
        blocks = {}
        if state == "OK":
            try:
                blocks = method.rank.read_task(roots[first], raw)
            except (KeyError, TypeError, ValueError):
                state = "INVALID_TASK"
        for condition in CONDITIONS:
            uid = pair[condition]
            src = data[uid]
            execution = {"task_state": state, "task_sha256": receipt["request_sha256"], "blocks": blocks,
                         "answers": {}}
            rows[uid] = {**{k: src[k] for k in ("uid", "group", "labels", "positions")},
                         "condition": condition, "primary": pair["primary"], "execution": execution,
                         "native": {arm: src["native"][arm] for arm in BASELINES}}
            if not blocks:
                continue
            draft = method.render(roots[uid], blocks, {}, {}, method.DRAFT)
            execution["answers"][method.DRAFT] = draft
            if any(x["kind"] == "CHOICE" for x in blocks.values()):
                pending.append((uid, SHARED, method.request(roots[uid], blocks)))
            else:
                execution["policy_state"] = "NO_DECISION"
                execution["answers"] = dict.fromkeys(method.MODES, draft)
    returned = stage(POLICY, pending)
    for uid, arm, wire in pending:
        rec, raw = returned[uid, arm]
        execution = rows[uid]["execution"]
        execution.update(policy_state=rec["status"], policy_sha256=sha(wire), raw_policy=raw)
        if rec["status"] != "OK":
            continue
        blocks = execution["blocks"]
        try:
            policy, matrices, rejected = method.read_matrix(roots[uid], blocks, raw)
        except (ValueError, TypeError, KeyError):
            execution["policy_state"] = "INVALID_POLICY"
            continue
        execution.update(policy=policy, matrices=matrices, rejected=rejected)
        execution["answers"].update({m: method.render(roots[uid], blocks, policy, matrices, m)
                                     for m in method.MODES[:-1]})
    return rows


def grade(rows, stage):
    author = prior.parent.prior.parent.joint.prior
    official = read(author.formal.OUT / "PLAN.json")
    cases = author.author_cases(official)
    scorer = prior.parent.prior.parent.joint.parent
    jobs = []
    for uid, row in rows.items():
        execution = row["execution"]
        for arm in method.MODES:
            row["native"][arm] = {"fields": {}, "status": execution.get("policy_state", execution["task_state"])}
            answer = execution["answers"].get(arm)
            if answer:
                jobs.append((uid, arm, scorer.grade_request(official, cases[uid], answer["answer"])))
    for (uid, arm), (rec, raw) in stage(JUDGE, jobs).items():
        row = rows[uid]
        row["native"][arm] = scorer.parse_grade(rec, raw, row["positions"])
        answers = row["execution"]["answers"]
        if arm == method.ANCHORED and answers.get(method.DIRECT, {}).get("answer") == answers[arm]["answer"]:
            row["native"][arm]["reuse"] = method.DIRECT


def summarize(spec, rows, ledger):
    primary = [row for row in rows.values() if row["primary"]]
    panels = {
        "primary": primary,
        **{name: [row for row in primary if row["condition"] == name] for name in CONDITIONS},
        "all_A": [row for row in primary if set(row["labels"]) == {"A"}],
        "contains_BC": [row for row in primary if set(row["labels"]) & {"B", "C"}],
        "active_guard": [row for row in primary if row["execution"].get("matrices")],
        "regression": [row for row in rows.values() if not row["primary"]],
    }
    compare = prior.parent.prior.parent.joint.parent.comparisons.grade_pair
    paired = {name: {arm: {"match": replay.paired(group, arm, method.ANCHORED),
                          **{metric: compare(group, arm, method.ANCHORED, metric)
                             for metric in ("OPB", "UPB", "FM", "VG", "full_match")}}
                     for arm in ARMS if arm != method.ANCHORED}
              for name, group in panels.items()}
    reach, changed = Counter(), []
    for row in rows.values():
        execution = row["execution"]
        prefix = "primary" if row["primary"] else "regression"
        reach[f"{prefix}/{execution.get('policy_state', execution['task_state'])}"] += 1
        role = row["condition"]
        matrix, answers = execution.get("matrices"), execution["answers"]
        if matrix:
            reach[f"{prefix}/{role}/has_matrix"] += 1
            for unit in matrix.values():
                for entry in unit["entries"].values():
                    for state in entry["checks"].values():
                        reach[f"{prefix}/{state['predicted']}/grounded_{state['exact_witness']}"] += 1
        if any(m not in answers for m in method.MODES):
            continue
        flags = {arm: answers[arm]["answer"] != answers[method.ANCHORED]["answer"]
                 for arm in (method.DIRECT, method.STATUS)}
        for arm, altered in flags.items():
            reach[f"{prefix}/different_from_{arm}"] += altered
        if any(flags.values()):
            changed.append({"uid": row["uid"], "group": row["group"], "primary": row["primary"],
                            "decisions": {m: answers[m]["decisions"] for m in method.MODES}, "difference": flags})
    gate, score = spec["screen"], paired["primary"][method.DIRECT]
    fm_interval = score["FM"].get("95pct_source_bootstrap")
    gates = {
        "coverage": score["match"]["valid_cases"] >= gate["valid_fraction"] * len(primary),
        "improves_feasibility": bool(fm_interval and fm_interval[1] < 0
                                     and score["FM"]["delta"] <= -gate["min_fm_improvement"]),
    }
    for panel, field in (("primary", "match"), ("all_A", "match"), ("contains_BC", "match"),
                         ("primary", "OPB"), ("contains_BC", "UPB"), ("primary", "VG")):
        cell = paired[panel][method.DIRECT][field]
        match = field == "match"
        n = cell.get("valid_cases" if match else "n", 0)
        delta = cell.get("match_delta" if match else "delta")
        gates[f"{panel}/{field}"] = bool(panels[panel] and n >= gate["valid_fraction"] * len(panels[panel])
                                         and delta is not None and (delta >= gate["protect_match"] if match
                                                                    else delta <= gate["protect_bias"]))
    anchor = paired["primary"][method.STATUS]["FM"]
    gates["anchor_adds_feasibility_benefit"] = anchor.get("delta", 0) < 0
    return {"gates": gates, "passed": all(gates.values()), "execution": reach, "changed": changed,
            "paired": paired, "common": {name: score_matrix(group, ARMS) for name, group in panels.items()},
            "usage": {n: usage([r for r in ledger if r["unit"]["stage"] == n]) for n in spec["caps"]}}


def execute(action, inputs):
    spec, _, _, _, archive = inputs
    live = action == "run"
    if spec != read(OUT / "FROZEN.json") or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen artifacts or service reference changed")
    exact = prior.cache(archive)
    exact[TASK] = read(prior.OUT / f"{TASK}_EXACT.json")
    exact[POLICY] = {}
    exact[JUDGE].update(read(prior.OUT / f"{JUDGE}_EXACT.json"))
    for records in exact.values():
        if any(digest != pair[0]["request_sha256"] for digest, pair in records.items()):
            raise ValueError("Inherited key differs from request receipt")
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        if len({sha(wire) for _, _, wire in jobs} - exact[name].keys()) > spec["caps"][name]:
            raise ValueError("Stage exceeds physical cap")
        if any(token_estimate(canonical(wire["messages"])) > 32768 for _, _, wire in jobs):
            raise ValueError("Request exceeds frozen input cap")
        result = replay.execute_stage(spec, "paired_receipts", name, jobs, exact[name], live)
        for uid, arm, wire in jobs:
            record, _ = result[uid, arm]
            if record["request_sha256"] != sha(wire) or record["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise RuntimeError(f"{name}: unmatched or unsettled receipt")
        return result

    path = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(path, {"state": "RUNNING", "caps": spec["caps"]})
    try:
        rows = generate(inputs, stage)
        grade(rows, stage)
        ledger = [r for name in spec["caps"] for r, _ in probe.stage_receipts(name).values()]
        probe.freeze(OUT / "SETTLED.json", {"rows": list(rows.values()), "ledger": ledger})
        probe.freeze(OUT / "RESULTS.json", summarize(spec, rows, ledger))
    except (ValueError, OSError, RuntimeError) as error:
        if live:
            probe.atomic_json(path, {"state": "STOPPED", "error": str(error)})
        raise
    if live:
        probe.atomic_json(path, {"state": "COMPLETE", "physical_requests": len(ledger)})


def check(inputs):
    spec, wires, _, roots, _ = inputs
    uid = next(iter(wires))
    root = roots[uid]
    anchor = root["public_task"]["query"]
    block = {"kind": "CHOICE", "anchor": anchor, "affected": "SELF", "display": 2, "conditional": False,
             "lines": ["Candidate without any specific documentation.", "Candidate using the specified material."]}
    blocks = method.rank.read_task(root, json.dumps({"blocks": [block]}))
    citation = next({"id": item["memory_id"], "quote": word.strip()}
                    for item in root["original_sources"]
                    for word in method.rank.draft.user_source(item["text"]) if word.strip())
    citation["quote"] = citation["quote"][:1000]
    matrix = {"conditions": ["specified material"], "candidates": []}
    for idx, quote in enumerate(("not in option or task", "using the specified material"), 1):
        matrix["candidates"].append({"option": f"O{idx}", "disposition": "DIRECT", "checks": [
            {"condition": 1, "status": "SUPPORTED", "location": "OPTION", "quote": quote}]})
    raw = {"decisions": [{"block": "D1", "preferences": [], "feasibility": matrix,
                          "guard": {"audience": "SELF", "sources": [citation], "exclude": [], "replacements": []}}]}
    policy, parsed, invalid = method.read_matrix(root, blocks, json.dumps(raw))
    assert not invalid
    render = lambda mode: method.render(root, blocks, policy, parsed, mode)["decisions"]["D1"]
    assert render(method.DIRECT)["routed"]["DIRECT"] == render(method.STATUS)["routed"]["DIRECT"] == ["O1", "O2"]
    assert render(method.ANCHORED)["routed"]["DIRECT"] == ["O2"]
    assert render(method.ANCHORED)["routed"]["CHECK"] == ["O1"]
    replay.manifest("offline", POLICY, [(uid, SHARED, method.request(root, blocks))])

    def mock(name, jobs):
        replay.manifest("offline", name, jobs)
        results = {}
        for unit, arm, wire in jobs:
            if name == TASK:
                assert json.loads(wire["messages"][1]["content"]) == {"task": roots[unit]["public_task"]}
                answer = json.dumps({"blocks": [{**block, "anchor": roots[unit]["public_task"]["query"]}]})
            else:
                answer = '{"decisions":[]}' if name == POLICY else None
            results[unit, arm] = {"status": "OK" if answer is not None else "OFFLINE",
                                  "request_sha256": sha(wire)}, answer
        return results

    rows = generate(inputs, mock)
    grade(rows, mock)
    assert len(rows) == 2 * len(spec["pairs"])
    assert not summarize(spec, rows, [])["passed"]
    print(json.dumps({"source_groups": spec["source_groups"], "families": len(wires), "cases": len(rows),
                      "task_cache_hits": spec["task_cache_hits"], "caps": spec["caps"], "new_requests": 0}))


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "freeze", "run", "report"))
    action = parser.parse_args().action
    inputs = prepare()
    if action in ("check", "freeze"):
        check(inputs)
        if action == "freeze":
            probe.freeze(OUT / "FROZEN.json", inputs[0])
    else:
        with probe.runner_lock(RUN / "runner.lock"):
            execute(action, inputs)
