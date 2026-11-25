"""Read durable ranking receipts and validate shared evidence, outputs, and costs."""
from argparse import ArgumentParser
from collections import Counter
import json
import re
from unittest.mock import patch

from deployment_cost import numeric_cost, old_cost, profile
import run_beneficiary_ranking as run


def live():
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    _, wires, _, roots, _ = run.prepare()
    expected = {run.sha(wire) for wire in wires.values()}
    manifest = run.read(run.OUT / f"{run.TASK}_MANIFEST.json")
    actual = set()
    for item in manifest["units"]:
        wire = item["request"]
        uid = item["unit"]["root_id"]
        if json.loads(wire["messages"][1]["content"]) != {"task": roots[uid]["public_task"]}:
            raise ValueError("The memory-blind request includes additional fields")
        actual.add(run.sha(wire))
    if actual != expected or len(actual) != len(manifest["units"]):
        raise ValueError("The task manifest differs from the frozen task roster")
    return {stage: Counter(rec["status"] if rec else "UNISSUED"
                           for rec, _ in run.probe.stage_receipts(stage).values())
            for stage in (run.TASK, run.POLICY, run.JUDGE)}


def embedded_rank(text):
    """Flag explicit text that can contradict a programmatic reorder."""
    marker = re.match(r"\s*(?:[*_#]+\s*)?(首选|优先推荐|第一推荐|备选|次选)", text)
    if marker is None:
        return None
    return "ALTERNATIVE" if marker[1] in ("备选", "次选") else "PREFERRED"


def choice_texts(block, guard):
    texts = {f"O{i}": line for i, line in enumerate(block["lines"], 1)}
    if guard:
        texts.update({f"G{i}": line for i, line in enumerate(guard["replacements"], 1)})
    return texts


def decision_behavior(rows, roots):
    method = run.method
    totals, warnings = Counter(), []
    for row in rows:
        uid, ex = row["uid"], row["execution"]
        scope = "primary" if row["primary"] else "regression"
        a, b, c = [ex["answers"].get(m) for m in (method.GENERIC, method.BOUNDED, method.TASK_ORDER)]
        if a is None or b is None or c is None:
            continue
        labels = dict(zip((s["memory_id"] for s in roots[uid]["original_sources"]), row["labels"], strict=True))
        guards = set()
        totals[f"{scope}/answered/{row['condition']}"] += 1
        totals[f"{scope}/bounded_answer_equals_task_order/{row['condition']}"] += b["answer"] == c["answer"]
        for slot in c["decisions"]:
            block = ex["blocks"][slot]
            detail = ex.get("policy", {}).get(slot, {})
            guard = detail.get("guard")
            if guard:
                guards.update(s["id"] for s in guard["sources"])
            texts = choice_texts(block, guard)
            order = {m: x["decisions"][slot]["shown"] for m, x in (
                (method.GENERIC, a), (method.BOUNDED, b), (method.TASK_ORDER, c))}
            if order[method.GENERIC][:1] != order[method.BOUNDED][:1]:
                totals[f"{scope}/first_choice_change/{row['condition']}"] += 1
                same_set = set(order[method.GENERIC]) == set(order[method.BOUNDED])
                totals[f"{scope}/first_choice_changes_with_same_set/{row['condition']}"] += same_set
            for arm in (method.GENERIC, method.BOUNDED, method.TASK_ORDER):
                markers = [embedded_rank(texts[key]) for key in order[arm]]
                if markers and (markers[0] == "ALTERNATIVE" or "PREFERRED" in markers[1:]):
                    totals[f"{scope}/embedded_rank_conflict/{arm}"] += 1
                    warnings.append({"uid": uid, "slot": slot, "arm": arm,
                                     "displayed": order[arm], "embedded_markers": markers})
        totals[f"{scope}/author_C_positions"] += sum(label == "C" for label in labels.values())
        totals[f"{scope}/author_C_cited_in_compiled_guards"] += sum(labels[s] == "C" for s in guards)
    return {
        "counts": totals, "lexical_rank_conflicts": warnings,
        "interpretation": "A warning means explicit text may contradict display order. A guard citation is not compliance.",
    }


def contrast_histories(spec, rows):
    """Pair both histories by the identical task and compare actual emitted choices."""
    modes = (run.method.GENERIC, run.method.BOUNDED, run.method.TASK_ORDER)
    totals, families = Counter(), []
    for pair in spec["pairs"]:
        a, b = (rows[pair[k]]["execution"] for k in ("all_A", "contains_BC"))
        if any(m not in output["answers"] for output in (a, b) for m in modes):
            continue
        result = {}
        for slot, block in a["blocks"].items():
            if block["kind"] != "CHOICE":
                continue
            options = []
            for state in (a, b):
                guard = state.get("policy", {}).get(slot, {}).get("guard")
                texts = choice_texts(block, guard)
                # G1 is a local replacement ID, so its wording must be compared.
                options.append({
                    mode: [run.sha(texts[k]) for k in state["answers"][mode]["decisions"][slot]["shown"]]
                    for mode in modes
                })
            result[slot] = {mode: {
                "first_changed_between_histories": options[0][mode][:1] != options[1][mode][:1],
                "displayed_set_changed_between_histories": set(options[0][mode]) != set(options[1][mode]),
            } for mode in modes}
        if not result:
            continue
        if pair["primary"]:
            totals["primary_families_with_two_observed_choice_sets"] += 1
            for mode in modes:
                totals[f"{mode}/primary_first_changes"] += any(
                    x[mode]["first_changed_between_histories"] for x in result.values())
                totals[f"{mode}/primary_displayed_set_changes"] += any(
                    x[mode]["displayed_set_changed_between_histories"] for x in result.values())
        families.append({"task_sha256": pair["task"], "source_group": pair["group"],
                         "primary": pair["primary"], "observed_differences": result})
    return {"counts": totals, "families": families}


def observed_behavior():
    inputs = run.prepare()
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    stages = {name: run.probe.stage_receipts(name) for name in (run.TASK, run.POLICY)}
    if not stages[run.POLICY]:
        raise ValueError("No second-stage manifest to replay")

    def available(name, jobs):
        output = {}
        for uid, arm, wire in jobs:
            rec, raw = stages[name][uid, arm]
            output[uid, arm] = (rec, raw) if raw else (
                {"status": "RESULT_UNAVAILABLE", "request_sha256": run.sha(wire)}, None)
        return output

    rows = run.generate(inputs, available)
    return {"partial": True, **decision_behavior(rows.values(), inputs[3]),
            "paired_history_behavior": contrast_histories(inputs[0], rows), "new_model_requests": 0}


def costs(rows, ledger, roots):
    reference = run.read(run.parent.prior.parent.joint.prior.formal.OUT / "PLAN.json")
    index = {(row["unit"]["stage"], row["request_sha256"]): row for row in ledger}
    modes = (run.method.GENERIC, run.method.BOUNDED, run.parent.GATE, run.parent.RP)
    bodies, counts = [], Counter()
    for row in rows:
        if not row["primary"]:
            continue
        ex = row["execution"]
        amounts = [numeric_cost(index[stage, ex[key]]["usage"])
                   for stage, key in ((run.TASK, "task_sha256"), (run.POLICY, "policy_sha256"))
                   if key in ex]
        usable = {}
        if amounts and all(a is not None for a in amounts):
            for arm in modes[:2]:
                if arm in ex["answers"]:
                    usable[arm] = sum(amounts, Counter())
                    counts[f"{arm}/{len(amounts)}"] += 1
        for arm in modes[2:]:
            value = old_cost(reference, roots[row["uid"]], arm)
            if value is not None:
                usable[arm] = value
        marks = {arm: row["native"][arm]["fields"]["match"]["matched"]
                 for arm in modes if "match" in row["native"][arm]["fields"]}
        if all(arm in usable and arm in marks for arm in modes):
            bodies.append({"group": row["group"], "usage": usable, "marks": marks,
                           "positions": row["positions"]})
    return {**profile(bodies, modes), "positions": sum(r["positions"] for r in bodies),
            "matched": {arm: sum(r["marks"][arm] for r in bodies) for arm in modes},
            "logical_inference_calls": counts, "judge_cost_excluded": True}


def score_component_sensitivity(rows, roots):
    """Remove only optional attribution text and reuse a score only for an exact prior answer."""
    method = run.method
    silent, variants, counts = "BOUNDED_WITHOUT_NOTE", [], Counter()
    recovered = []
    for row in rows:
        uid, ex = row["uid"], row["execution"]
        native = dict(row["native"])
        target = ex["answers"].get(method.BOUNDED)
        if target is None or not any(item["conditional"] is not None for item in target["decisions"].values()):
            native[silent] = native[method.BOUNDED]
        else:
            blocks = {slot: {**block, "conditional": False} if block["kind"] == "CHOICE" else block
                      for slot, block in ex["blocks"].items()}
            changed = method.render(roots[uid], blocks, ex["policy"], method.BOUNDED)
            old_ids = {slot: (item["shown"], item["excluded"]) for slot, item in target["decisions"].items()}
            new_ids = {slot: (item["shown"], item["excluded"]) for slot, item in changed["decisions"].items()}
            if old_ids != new_ids:
                raise ValueError("Attribution ablation changed a candidate decision")
            matching = [arm for arm, answer in ex["answers"].items() if answer["answer"] == changed["answer"]]
            alias = next((arm for arm in matching if native[arm]["fields"].get("match")), None)
            if alias is None and matching:
                alias = matching[0]
            native[silent] = native[alias] if alias is not None else {"fields": {}, "status": "NO_EXACT_SCORE"}
            counts["attribution_changed"] += 1
            counts["same_wire_score_available"] += bool(alias and native[alias]["fields"].get("match"))
            recovered.append({"uid": uid, "primary": row["primary"], "exact_answer_alias": alias,
                              "alternate_answer_sha256": run.sha(changed["answer"])})
        variants.append({**row, "native": native})

    comparisons = {}
    fields_score = run.parent.prior.parent.joint.parent.comparisons.grade_pair
    for panel in ("primary", "all_A", "contains_BC"):
        subset = [row for row in variants if row["primary"] and (panel == "primary" or row["condition"] == panel)]
        comparisons[panel] = {}
        for left, right in ((method.DRAFT, method.TASK_ORDER), (method.GENERIC, silent),
                            (method.TASK_ORDER, silent), (method.BOUNDED, silent)):
            comparisons[panel][f"{left}/{right}"] = {
                "match": run.replay.paired(subset, left, right),
                **{f: fields_score(subset, left, right, f) for f in ("OPB", "UPB", "FM", "VG")},
            }
    return {"counts": counts, "attribution_changes": recovered, "comparisons": comparisons,
            "interpretation": "Attribution ablation is post hoc. Unseen text gets no new grade or estimated score."}


def verify():
    spec, _, _, roots, _ = inputs = run.prepare()
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("Expected a completed comparison")
    checked = []

    def replay_again(path, rebuilt):
        if json.loads(json.dumps(rebuilt)) != run.read(path):
            raise ValueError(f"Replay differs from {path.name}")
        checked.append(path.name)

    with patch.object(run.probe, "freeze", replay_again):
        run.execute("report", inputs)
    settled = run.read(run.OUT / "SETTLED.json")
    ledger = [rec for stage in spec["caps"] for rec, _ in run.probe.stage_receipts(stage).values()]
    unique = {(row["unit"]["stage"], row["request_sha256"]) for row in ledger}
    if not ledger == settled["ledger"] or len(unique) != len(ledger) or len(unique) != state["physical_requests"]:
        raise ValueError("Mismatch in physical receipt accounting")
    rows = {row["uid"]: row for row in settled["rows"]}
    for pair in spec["pairs"]:
        a, b = (rows[pair[key]]["execution"] for key in ("all_A", "contains_BC"))
        if a["task_sha256"] != b["task_sha256"] or a["blocks"] != b["blocks"]:
            raise ValueError("Both natural histories must share the same immutable choice set")

    scope_change, summaries = [], Counter()
    left, right, default = run.method.GENERIC, run.method.BOUNDED, run.method.TASK_ORDER
    for row in rows.values():
        ex = row["execution"]
        a, b, c = (ex["answers"].get(mode) for mode in (left, right, default))
        if a is None or b is None or c is None:
            continue
        if a["answer"] == b["answer"] and row["native"][left]["fields"] != row["native"][right]["fields"]:
            raise ValueError("Same rendered answer must reuse equal grading fields")
        for slot, middle in b["decisions"].items():
            ordinary, baseline = a["decisions"][slot], c["decisions"][slot]
            if middle["excluded"] != ordinary["excluded"] or middle["excluded"] != baseline["excluded"]:
                raise ValueError("Hard failures must be excluded identically in each arm")
            if len({len(v["shown"]) for v in (ordinary, middle, baseline)}) != 1:
                raise ValueError("An arm modified the number of shown options")
            if ordinary != middle:
                summaries[ex["blocks"][slot]["affected"]] += 1
                scope_change.append({
                    "uid": row["uid"], "group": row["group"], "primary": row["primary"],
                    "condition": row["condition"], "slot": slot,
                    "affected": ex["blocks"][slot]["affected"],
                    "executable_choices": {left: ordinary, right: middle, default: baseline},
                    "fields": {mode: row["native"][mode]["fields"] for mode in (left, right, default)},
                })
    return {"verified": checked, "physical_requests": len(ledger), "changes": scope_change,
            "changed_decisions_by_affected": summaries,
            "primary_generation_cost": costs(list(rows.values()), ledger, roots),
            "decision_behavior": decision_behavior(rows.values(), roots),
            "paired_history_behavior": contrast_histories(spec, rows),
            "component_sensitivity": score_component_sensitivity(rows.values(), roots),
            "new_model_requests": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("live", "verify", "behavior"))
    args = parser.parse_args()
    task = {"live": live, "verify": verify, "behavior": observed_behavior}[args.action]
    print(json.dumps(task(), ensure_ascii=False, indent=2))
