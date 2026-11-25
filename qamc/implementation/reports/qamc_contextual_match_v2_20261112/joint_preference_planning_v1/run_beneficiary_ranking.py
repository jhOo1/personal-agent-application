"""Compare choice ranking on paired natural histories of the same exposed task."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path

from qamc.common import canonical, sha, token_estimate

import beneficiary_ranking as method
import recover_decision_repair_drafts as recovery
import run_decision_repair as parent
from analyze_policy import group_stability
from settle_joint_planning import score_matrix, usage


OUT = parent.OUT.with_name("beneficiary_ranking_rpeval_v1")
RUN = parent.RUN.with_name(OUT.name)
TASK, POLICY, JUDGE = "RankTask", "RankPolicy", parent.JUDGE
probe, replay, read = parent.probe, parent.replay, parent.read
SHARED = parent.prior.SHARED
DIAGNOSTIC_SUFFIXES = ("explicit/054", "implicit/100", "explicit/008")
CONTROLS = (parent.GATE, parent.RP, *[x for x in method.MODES if x != method.BOUNDED])


def prepare():
    inventory_path = parent.OUT / "SHARED_DECISION_INVENTORY.json"
    inventory = read(inventory_path)
    parent_spec, _, roots, originals, _, archive = parent.prior.prepare("pilot")
    by_uid = {r["uid"]: r for r in originals}
    early = read(parent.prior.BASE_OUT / "smoke/FROZEN.json")
    associated = {"explicit/003", "explicit/008", "explicit/089", "implicit/136", "explicit/086"}
    excluded = set(parent_spec["diagnostic_source_groups"]) | set(early["panel"].values())
    excluded.update(r["group"] for r in originals
                    if any(r["uid"].endswith(suffix) for suffix in associated))
    panels, groups = [], set()
    families = sorted(inventory["per_task"], key=lambda family: sha(["rank-v1", family["task_sha256"]]))
    for family in families:
        variants = family["history_variants"]
        diagnosis = next((uid for cond in variants.values() for uid in cond
                          if uid.endswith(DIAGNOSTIC_SUFFIXES)), None)
        group = family["source_group"]
        primary = group not in excluded and group not in groups
        if not primary and diagnosis is None:
            continue
        chosen = {}
        for condition, candidates in variants.items():
            chosen[condition] = diagnosis if diagnosis in candidates else min(
                candidates, key=lambda uid: sha(["rank-v1-variant", uid]))
        panels.append({"task": family["task_sha256"], "group": group, "primary": primary, **chosen})
        if primary:
            groups.add(group)
    if len(groups) != 18 or len(panels) != 21:
        raise ValueError("Unexpected exposed pair schedule")
    wires, rows = {}, {}
    for cell in panels:
        a, b = (cell[key] for key in ("all_A", "contains_BC"))
        if a in rows or b in rows:
            raise ValueError("Duplicate task variant")
        if (roots[a]["public_task"] != roots[b]["public_task"]
                or roots[a]["task_wire_sha256"] != roots[b]["task_wire_sha256"]
                or sha(roots[a]["original_sources"]) == sha(roots[b]["original_sources"])):
            raise ValueError("Invalid task or history pairing")
        wires[a] = method.task_request(roots[a])
        rows.update({a: by_uid[a], b: by_uid[b]})
    base = Path(__file__).resolve().parents[3]
    files = (Path(__file__), Path(method.__file__), Path(method.draft.__file__),
             Path(method.grounded.__code__.co_filename),
             Path(method.planning.__file__), Path(replay.__file__), Path(replay.prior.__file__),
             Path(__file__).with_name("BENEFICIARY_RANKING_PROTOCOL.md"), inventory_path,
             parent.prior.BASE_OUT / "pilot/FROZEN.json", parent.prior.parent.OUT / "SETTLED.json",
             parent.prior.parent.joint.prior.OUT / "FROZEN.json",
             parent.prior.parent.joint.prior.formal.OUT / "PLAN.json")
    spec = {
        "pairs": panels, "caps": {TASK: len(wires), POLICY: len(rows), JUDGE: 4 * len(rows)},
        "service_reference_sha256": parent_spec["service_reference_sha256"],
        "inputs_sha256": {str(path.resolve().relative_to(base)): sha(path.read_bytes()) for path in files},
        "shared_task_requests": {uid: sha(wire) for uid, wire in wires.items()},
        "screen": {"common_coverage": .90, "match_gain": .05, "protection_match_delta": -.02,
                   "protection_loss_delta": .05},
        "independent_confirmation": False,
    }
    return spec, wires, rows, roots, archive


def generate(inputs, stage):
    spec, wires, source, roots, _ = inputs
    task_receipts = stage(TASK, [(uid, SHARED, wire) for uid, wire in wires.items()])
    results, inputs_round_two = {}, []
    for pair in spec["pairs"]:
        first = pair["all_A"]
        rec, raw = task_receipts[first, SHARED]
        task_status = rec["status"]
        blocks = {}
        if task_status == "OK":
            try:
                blocks = method.read_task(roots[first], raw)
            except (KeyError, TypeError, ValueError):
                task_status = "INVALID_TASK"
        for condition in ("all_A", "contains_BC"):
            uid = pair[condition]
            archived = source[uid]
            state = {"task_status": task_status, "task_sha256": rec["request_sha256"],
                     "answers": {}, "blocks": blocks}
            results[uid] = {
                "uid": uid, "family": pair["task"], "group": pair["group"], "primary": pair["primary"],
                "condition": condition, "labels": archived["labels"], "positions": archived["positions"],
                "native": {arm: archived["native"][arm] for arm in (parent.GATE, parent.RP)}, "execution": state,
            }
            if not blocks:
                continue
            state["answers"][method.DRAFT] = method.render(roots[uid], blocks, {}, method.DRAFT)
            if any(block["kind"] == "CHOICE" for block in blocks.values()):
                inputs_round_two.append((uid, SHARED, method.history_request(roots[uid], blocks)))
            else:
                state["policy_status"] = "NO_DECISION"
                state["answers"] = {mode: state["answers"][method.DRAFT] for mode in method.MODES}
    received = stage(POLICY, inputs_round_two)
    for uid, arm, wire in inputs_round_two:
        rec, raw = received[uid, arm]
        state = results[uid]["execution"]
        state.update(policy_status=rec["status"], policy_raw=raw, policy_sha256=sha(wire))
        if rec["status"] != "OK":
            continue
        blocks = state["blocks"]
        choices = {slot: block for slot, block in blocks.items() if block["kind"] == "CHOICE"}
        try:
            policy, rejected = method.read_policy(roots[uid], choices, raw)
        except (KeyError, TypeError, ValueError):
            state["policy_status"] = "INVALID_POLICY"
            continue
        state.update(policy=policy, rejected=rejected)
        for mode in method.MODES[:-1]:
            state["answers"][mode] = method.render(roots[uid], blocks, policy, mode)
    return results


def grade(results, stage):
    author = parent.prior.parent.joint.prior
    reference = read(author.formal.OUT / "PLAN.json")
    cases = author.author_cases(reference)
    scorer = parent.prior.parent.joint.parent
    jobs = []
    for uid, row in results.items():
        state = row["execution"]
        for arm in method.MODES:
            row["native"][arm] = {"fields": {}, "status": state.get("policy_status", state["task_status"])}
            if arm in state["answers"]:
                text = state["answers"][arm]["answer"]
                jobs.append((uid, arm, scorer.grade_request(reference, cases[uid], text)))
    for (uid, arm), (rec, raw) in stage(JUDGE, jobs).items():
        row = results[uid]
        row["native"][arm] = scorer.parse_grade(rec, raw, row["positions"])
        answers = row["execution"]["answers"]
        if arm == method.BOUNDED and answers.get(method.GENERIC, {}).get("answer") == answers[arm]["answer"]:
            row["native"][arm]["reuse"] = method.GENERIC


def family_interaction(spec, results):
    groups, totals = {}, Counter()
    for pair in spec["pairs"]:
        if not pair["primary"]:
            continue
        contrasts = {}
        for cond in ("all_A", "contains_BC"):
            row = results[pair[cond]]
            marks = [row["native"][arm]["fields"].get("match") for arm in (method.GENERIC, method.BOUNDED)]
            if not all(marks):
                break
            a, b = marks
            contrasts[cond] = (b["matched"] - a["matched"]) / row["positions"]
        if len(contrasts) == 2:
            contrast = contrasts["contains_BC"] - contrasts["all_A"]
            groups[pair["group"]] = [contrast, 1]
            totals["paired_tasks"] += 1
            totals["contains_BC_improves_more"] += contrast > 0
    return {**totals, "equal_task_weighted_gap": (sum(x[0] for x in groups.values()) / len(groups)
                                               if groups else None),
            **group_stability(groups)}


def summarize(spec, results, ledger):
    primary = [r for r in results.values() if r["primary"]]
    panels = {"primary": primary, "all_A": [r for r in primary if r["condition"] == "all_A"],
              "contains_BC": [r for r in primary if r["condition"] == "contains_BC"]}
    compare = parent.prior.parent.joint.parent.comparisons.grade_pair
    stats = {key: {arm: {"match": replay.paired(group, arm, method.BOUNDED),
                        **{f: compare(group, arm, method.BOUNDED, f)
                           for f in ("OPB", "UPB", "FM", "VG", "full_match")}}
                    for arm in CONTROLS} for key, group in panels.items()}
    primary_match = stats["primary"][method.GENERIC]["match"]
    screen, ci = spec["screen"], primary_match.get("95pct_source_bootstrap")
    gates = {"coverage": primary_match["valid_cases"] >= screen["common_coverage"] * len(primary),
             "overall": bool(ci and ci[0] > 0
                             and primary_match.get("match_delta", 0) >= screen["match_gain"])}
    for key, field in (("all_A", "match"), ("contains_BC", "match"), ("primary", "OPB"),
                       ("contains_BC", "UPB"), ("primary", "FM"), ("primary", "VG")):
        record = stats[key][method.GENERIC][field]
        lower_is_better = field != "match"
        delta = record.get("delta" if lower_is_better else "match_delta")
        n = record.get("n" if lower_is_better else "valid_cases", 0)
        gates[f"{key}/{field}"] = bool(delta is not None and n >= screen["common_coverage"] * len(panels[key])
                                      and (delta <= screen["protection_loss_delta"] if lower_is_better
                                           else delta >= screen["protection_match_delta"]))
    execute = Counter()
    for row in results.values():
        state = row["execution"]
        execute[f"{row['condition']}/{state.get('policy_status', state['task_status'])}"] += 1
        answers = state["answers"]
        if all(m in answers for m in method.MODES):
            each = {m: answers[m]["decisions"] for m in method.MODES}
            if answers[method.GENERIC]["answer"] != answers[method.BOUNDED]["answer"]:
                execute["pair_text_diff"] += 1
            for slot in each[method.BOUNDED]:
                a, b, base = (each[m][slot]["shown"] for m in (method.GENERIC, method.BOUNDED, method.TASK_ORDER))
                execute["first_choice_diff"] += a[:1] != b[:1]
                execute["bounded_diff_from_task_default"] += b[:1] != base[:1]
                execute["shown_counts_differ"] += len(a) != len(b)
    return {"paired": stats, "strict_common": {key: score_matrix(group, (*CONTROLS, method.BOUNDED))
                                               for key, group in panels.items()},
            "execution": execute, "same_task_history_interaction": family_interaction(spec, results),
            "gates": gates, "passed": all(gates.values()),
            "usage": {name: usage([r for r in ledger if r["unit"]["stage"] == name]) for name in spec["caps"]}}


def cache(archive):
    existing = parent.inherited(archive)[parent.JUDGE]
    for directory in (parent.OUT, recovery.OUT):
        for digest, entry in read(directory / f"{JUDGE}_EXACT.json").items():
            if digest != entry[0]["request_sha256"]:
                raise ValueError("Old scorer receipt mismatch")
            existing.setdefault(digest, entry)
    return {TASK: {}, POLICY: {}, JUDGE: existing}


def execute(action, inputs):
    spec, _, _, _, archive = inputs
    live = action == "run"
    if read(OUT / "FROZEN.json") != spec or (live and probe.read_reference()[1] != spec["service_reference_sha256"]):
        raise ValueError("Frozen inputs or service reference changed")
    exact = cache(archive)
    probe.OUT, probe.RUN, replay.OUT = OUT, RUN, OUT

    def stage(name, jobs):
        if len({sha(wire) for _, _, wire in jobs} - exact[name].keys()) > spec["caps"][name]:
            raise ValueError("Request cap exceeded")
        if any(token_estimate(canonical(wire["messages"])) > 32768 for _, _, wire in jobs):
            raise ValueError("A wire exceeds the frozen input limit")
        observed = replay.execute_stage(spec, "exposed_paired", name, jobs, exact[name], live)
        for uid, arm, wire in jobs:
            rec, _ = observed[uid, arm]
            if rec["request_sha256"] != sha(wire) or rec["status"] == "PENDING_DELIVERY_UNKNOWN":
                raise RuntimeError(f"{name}: unmatched or unsettled receipt")
        return observed

    state = OUT / "RUN_STATE.json"
    if live:
        probe.atomic_json(state, {"state": "RUNNING", "caps": spec["caps"]})
    try:
        results = generate(inputs, stage)
        grade(results, stage)
        ledger = [rec for phase in spec["caps"] for rec, _ in probe.stage_receipts(phase).values()]
        probe.freeze(OUT / "SETTLED.json", {"rows": list(results.values()), "ledger": ledger})
        probe.freeze(OUT / "RESULTS.json", summarize(spec, results, ledger))
    except (ValueError, RuntimeError, OSError) as exc:
        if live:
            probe.atomic_json(state, {"state": "STOPPED", "error": str(exc)})
        raise
    if live:
        probe.atomic_json(state, {"state": "COMPLETE", "physical_requests": len(ledger)})


def check(inputs):
    spec, wires, rows, roots, _ = inputs
    assert len(wires) == 21 and len(rows) == 42
    uid = next(iter(rows))
    root = roots[uid]
    option = {"kind": "CHOICE", "affected": "SHARED", "anchor": root["public_task"]["query"],
              "display": 2, "conditional": True, "lines": ["Use the task-backed option.", "Use the personal option."]}
    blocks = method.read_task(root, json.dumps([option]))
    assert json.loads(wires[uid]["messages"][1]["content"]) == {"task": root["public_task"]}
    citation = next({"id": s["memory_id"], "quote": quote.strip()} for s in root["original_sources"]
                    for quote in method.draft.user_source(s["text"]) if 0 < len(quote.strip()) <= 1000)
    preference = {"option": "O2", "source": citation, "authority": "PERSONAL", "delegation": None}
    proposal = {"block": "D1", "guard": None, "preferences": [preference]}
    checked, invalid = method.read_policy(root, blocks, json.dumps({"decisions": [proposal]}))
    assert not invalid
    outputs = {arm: method.render(root, blocks, checked, arm)["decisions"]["D1"] for arm in method.MODES}
    assert outputs[method.GENERIC]["shown"] == ["O2", "O1"]
    assert outputs[method.BOUNDED] == {"shown": ["O1", "O2"], "excluded": [], "conditional": "O2"}
    assert outputs[method.TASK_ORDER]["conditional"] is None
    for affected, expected in (("OTHER", ["O1", "O2"]), ("SELF", ["O2", "O1"])):
        test = {"D1": {**option, "affected": affected}}
        actual = method.render(root, test, checked, method.BOUNDED)["decisions"]["D1"]
        assert actual["shown"] == expected and actual["conditional"] is None
    guard = {"audience": "PARTICIPANT", "sources": [citation], "exclude": ["O1", "O2"],
             "replacements": ["A compliant alternative."]}
    proposal["guard"] = guard
    checked, invalid = method.read_policy(root, blocks, json.dumps({"decisions": [proposal]}))
    assert not invalid
    for arm in (method.GENERIC, method.BOUNDED, method.TASK_ORDER):
        assert method.render(root, blocks, checked, arm)["decisions"]["D1"]["shown"] == ["G1"]
    guard.update(replacements=[])
    checked, _ = method.read_policy(root, blocks, json.dumps([proposal]))
    assert method.render(root, blocks, checked, method.BOUNDED)["decisions"]["D1"]["shown"] == []
    guard["replacements"] = [option["lines"][0]]
    checked, _ = method.read_policy(root, blocks, json.dumps([proposal]))
    assert method.render(root, blocks, checked, method.BOUNDED)["decisions"]["D1"]["shown"] == []

    def mock(name, jobs):
        replay.manifest("offline", name, jobs)
        output = {}
        for u, arm, wire in jobs:
            if name == TASK:
                answer = json.dumps({"blocks": [{**option, "anchor": roots[u]["public_task"]["query"]}]})
            elif name == POLICY:
                answer = '{"decisions":[]}'
            else:
                answer = None
            status = "OK" if answer is not None else "OFFLINE"
            output[u, arm] = {"status": status, "request_sha256": sha(wire)}, answer
        return output

    results = generate(inputs, mock)
    grade(results, mock)
    assert len(results) == 42 and all(len(r["execution"]["answers"]) == 4 for r in results.values())
    assert not summarize(spec, results, [])["passed"]
    print(json.dumps({"paired_tasks": len(wires), "variants": len(rows), "caps": spec["caps"], "new_requests": 0}))


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
