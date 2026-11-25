"""Audit saved proposals, independently committed variants, and matched cost."""
from argparse import ArgumentParser
from collections import Counter
import json
from statistics import median

from qamc.common import sha

from deployment_cost import numeric_cost, old_cost, profile
import run_decision_transactions as run


def reasoning_tokens(receipt):
    details = receipt.get("usage_numeric_details") or {}
    reasoning = (details.get("completion_tokens_details") or {}).get("reasoning_tokens")
    completion = (receipt.get("usage") or {}).get("completion_tokens")
    if type(reasoning) is int and type(completion) is int and 0 <= reasoning <= completion:
        return reasoning
    return None


def audit(panel, settled, inputs):
    _, _, roots, data, inherited = inputs
    method = run.method
    receipts = {key: receipt for key, (receipt, _) in inherited[run.STAGE].items()}
    receipts.update({r["request_sha256"]: r for r in settled["ledger"] if r["unit"]["stage"] == run.STAGE})
    counts, label_counts, rejection_stage, source_roles, changes = Counter(), Counter(), Counter(), Counter(), []
    costs = {arm: [] for arm in (method.ATOMIC, method.ORDINARY)}
    decomposition = {arm: Counter() for arm in costs}
    detailed_pairs = 0
    arms = (*costs, *run.ARCHIVED[1:])
    deployment = []
    if panel == "pilot":
        archive = run.previous.prior.prepare()[4]
        drafts = run.previous.task_only.saved_drafts(archive)
        author = run.previous.prior.old.prior.parent.prior.parent.joint.prior
        official = run.read(author.formal.OUT / "PLAN.json")
    for row in settled["rows"]:
        uid = row["uid"]
        root = roots[uid]
        sources = root["original_sources"]
        labels = dict(zip((s["memory_id"] for s in sources), row["labels"], strict=True))
        if list(labels) != [f"M{i}" for i in range(len(sources))]:
            raise ValueError(f"Unaligned source labels for {uid}")
        outputs = row["outputs"]
        if method.ATOMIC not in outputs:
            counts["proposal_unavailable"] += 1
            continue
        units = {u["index"]: u for u in row["units"]}
        draft = method.rank.render(root, data[uid]["blocks"], {}, method.rank.DRAFT)["answer"]
        counts["compiled"] += 1
        counts["decisions_with_alternatives"] += sum(len(u["variants"]) > 1 for u in units.values())
        counts.update(f"contract/{r['reason']}" for r in row["rejected"])
        proposal = method.rank.model_object(row["attempts"][method.ATOMIC]["raw"], "decisions")
        requested_sources = set()
        for unit in proposal["decisions"]:
            if not isinstance(unit, dict) or not isinstance(unit.get("effects"), list):
                continue
            for effect in unit["effects"]:
                source = effect.get("source") if isinstance(effect, dict) else None
                if isinstance(source, dict) and isinstance(source.get("id"), str):
                    requested_sources.add(source["id"])
        covered = {u["effects"][key]["source"]["id"] for u in units.values()
                   for v in u["variants"] for key in v["effects"]}
        permitted = {u["effects"][key]["source"]["id"] for u in units.values()
                     for v in u["variants"] for key in v["effects"] if method.scoped.permitted(u["effects"][key])}
        usable = {u["effects"][key]["source"]["id"] for u in units.values()
                  if (selected := method.select(u, True)) is not None for key in selected["effects"]}
        for source, label in labels.items():
            label_counts[f"{label}/eligible"] += 1
            label_counts[f"{label}/proposed"] += source in requested_sources
            label_counts[f"{label}/valid_variant"] += source in covered
            label_counts[f"{label}/individually_permitted"] += source in permitted
            label_counts[f"{label}/picked_in_complete_variant"] += source in usable
            stage = next((name for name, candidates in (
                ("not_proposed", requested_sources), ("invalid_variant", covered),
                ("role_or_force", permitted), ("no_selected_complete_variant", usable))
                if source not in candidates), "selected_complete_variant")
            rejection_stage[f"{label}/{stage}"] += 1

        commits_by_arm = {}
        for arm in (method.ATOMIC, method.BUNDLED):
            execution = row["execution"][arm]
            counts[f"{arm}/changes_draft"] += outputs[arm] != draft
            counts.update({f"{arm}/rejected/{k}": v for k, v in execution["rejected"].items()})
            applied = [units[c["decision"]]["effects"][key]
                       for c in execution["committed"] for key in c["effects"]]
            effect_sources = {effect["source"]["id"] for effect in applied}
            roles = {(effect["source"]["id"], effect["site"], effect["force"]) for effect in applied}
            source_roles.update(f"{arm}/{labels[source]}/{site}/{force}" for source, site, force in roles)
            for label in ("A", "B", "C"):
                label_counts[f"{label}/{arm}/committed"] += sum(labels[s] == label for s in effect_sources)
            commits_by_arm[arm] = [{"memory_id": sid, "author": labels[sid]} for sid in sorted(effect_sources)]

        if outputs[method.ATOMIC] != outputs[method.BUNDLED]:
            changes.append({"uid": uid, "group": row["group"], "committed_sources": commits_by_arm,
                            "commit_trace": row["execution"], "native": {
                                 arm: row["native"][arm]["fields"] for arm in method.MODES}})
        if not all(row["native"].get(arm, {}).get("fields", {}).get("match") for arm in costs):
            continue
        records = {arm: receipts[row["attempts"][arm]["request_sha256"]] for arm in costs}
        priced = {arm: numeric_cost(r["usage"]) for arm, r in records.items()}
        if any(price is None for price in priced.values()):
            continue
        for arm in costs:
            costs[arm].append((priced[arm], records[arm].get("elapsed_seconds")))
        reasoning = {arm: reasoning_tokens(record) for arm, record in records.items()}
        if all(value is not None for value in reasoning.values()):
            detailed_pairs += 1
            for arm, value in reasoning.items():
                cost = priced[arm]
                decomposition[arm].update({
                    "prompt_tokens": cost["prompt_tokens"], "reported_reasoning_tokens": value,
                    "completion_minus_reported_reasoning": cost["completion_tokens"] - value,
                    "reported_total_tokens": cost["total_tokens"],
                    "reported_completion_over_requested": records[arm].get("reported_completion_over_requested") is True,
                })
        if panel == "pilot" and all(row["native"][arm]["fields"].get("match") for arm in arms):
            draft = numeric_cost(drafts[row["draft_origin"]]["record"]["usage"])
            observed = {arm: old_cost(official, root, arm) for arm in run.ARCHIVED[1:]}
            if draft is not None and all(value is not None for value in observed.values()):
                usage = {arm: draft + priced[arm] for arm in costs}
                usage.update(observed)
                deployment.append({"group": row["group"], "positions": row["positions"], "usage": usage,
                                   "match": {arm: row["native"][arm]["fields"]["match"]["matched"] for arm in arms}})

    summary = {}
    for arm, values in costs.items():
        latency = [elapsed for _, elapsed in values if isinstance(elapsed, (int, float))]
        summary[arm] = {"matched_histories": len(values), "stage_tokens": sum(v[0]["total_tokens"] for v in values),
                        "median_stage_seconds": median(latency) if latency else None}
    matched = {}
    if deployment:
        matched = {**profile(deployment, arms), "positions": sum(row["positions"] for row in deployment),
                   "matched": {arm: sum(row["match"][arm] for row in deployment) for arm in arms},
                   "includes_task_draft": True, "includes_judge": False}
    return {"panel": panel, "counts": counts, "author_source_positions": label_counts,
            "author_first_unreached_stage": rejection_stage,
            "committed_source_role_and_force": source_roles,
            "changes": changes, "matched_composition_usage": summary,
            "matched_composition_numeric_breakdown": {"histories": detailed_pairs, "arms": decomposition},
            "composition_excludes_common_draft_and_judge": True,
            "matched_full_deployment_usage": matched, "new_requests": 0}


def observed_generation(panel, inputs, out):
    spec, _, _, _, inherited = inputs
    if run.read(out / "FROZEN.json") != spec or run.read(out / "RUN_STATE.json")["state"] != "RUNNING":
        raise ValueError("A snapshot requires the running frozen experiment")
    run.probe.OUT, run.probe.RUN = out, run.BASE_RUN / panel
    local = {r["request_sha256"]: (r, raw) for r, raw in run.probe.stage_receipts(run.STAGE).values() if r}
    known = {**inherited[run.STAGE], **local}

    def saved(_, jobs):
        available = {}
        for uid, arm, wire in jobs:
            digest = sha(wire)
            available[uid, arm] = known.get(digest, ({"status": "UNISSUED", "request_sha256": digest}, None))
        return available

    rows = run.generate(inputs, saved)
    return {"rows": list(rows.values()), "ledger": [record for record, _ in local.values()]}


def snapshot(panel, inputs, out):
    observed = observed_generation(panel, inputs, out)
    for row in observed["rows"]:
        # A running score/answer comparison has no fixed denominator.
        row["native"].update({arm: {"fields": {}} for arm in run.method.MODES})
    report = audit(panel, observed, inputs)
    report["snapshot"] = True
    report["physical_receipt_statuses"] = Counter(record["status"] for record in observed["ledger"])
    return report


def scored_subgroups(rows):
    """Disentangle supporting preferences from histories with hard constraints."""
    panels = {"all_A": [], "B_without_C": [], "contains_C": []}
    fm_strata = {"draft_FM_zero": [], "draft_FM_above_zero": []}
    compared = (run.ARCHIVED[0], run.method.ATOMIC, run.method.BUNDLED, run.method.ORDINARY)
    for row in rows:
        labels = set(row["labels"])
        panel = "contains_C" if "C" in labels else "B_without_C" if "B" in labels else "all_A"
        panels[panel].append(row)
        fm = {arm: row["native"][arm]["fields"].get("FM") for arm in compared}
        if labels & {"B", "C"} and all(isinstance(value, (int, float)) for value in fm.values()):
            key = "draft_FM_above_zero" if fm[run.ARCHIVED[0]] > 0 else "draft_FM_zero"
            fm_strata[key].append({"uid": row["uid"], "group": row["group"], "FM": fm})
    return {
        "native_common_by_author_intent": {name: run.score_matrix(panel, run.ARMS) for name, panel in panels.items()},
        "contains_BC_fm_strata": {name: {"histories": len(panel),
                                        "source_groups": len({r["group"] for r in panel}),
                                        "totals": {arm: sum(r["FM"][arm] for r in panel) for arm in compared},
                                        "rows": panel} for name, panel in fm_strata.items()},
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("panel", choices=("smoke", "pilot"))
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    out = run.BASE_OUT / args.panel
    inputs = run.prepare(args.panel)
    if args.snapshot:
        report = snapshot(args.panel, inputs, out)
    else:
        if run.read(out / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Run has not settled")
        settled = run.read(out / "SETTLED.json")
        report = {**audit(args.panel, settled, inputs), **scored_subgroups(settled["rows"])}
    print(json.dumps(report, ensure_ascii=False, indent=2))
