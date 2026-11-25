"""Measure changed decisions and source use from exact effect-compiler receipts."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from deployment_cost import numeric_cost, old_cost, profile
import run_effect_scope as run


def observed(inputs):
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    known = dict(inputs[-1])
    for record, raw in run.probe.stage_receipts(run.STAGE).values():
        if record:
            known[record["request_sha256"]] = (record, raw)

    def snapshot(_, jobs):
        return {(uid, arm): known.get(run.sha(wire), (
            {"status": "UNISSUED", "request_sha256": run.sha(wire)}, None))
                for uid, arm, wire in jobs}

    return list(run.generate(inputs, snapshot).values())


def rejected_anchors(row, root):
    """Trace role effects that did not have task and user-source witnesses."""
    method = run.method
    raw = row["attempts"][method.STRUCTURAL]["raw"]
    proposal = method.rank.model_object(raw, "effects")
    memories = {item["memory_id"]: item["text"] for item in root["original_sources"]}
    task = tuple(method.rank.draft.task_text(root["public_task"]))
    resolutions = []
    for item in proposal["effects"]:
        if not isinstance(item, dict) or set(item) != method.EFFECT_FIELDS:
            continue
        key, source, task_quote = (item[field] for field in ("id", "source", "task_quote"))
        if not isinstance(key, str) or key in row["effects"] or not isinstance(source, dict):
            continue
        source_id, quote = source.get("id"), source.get("quote")
        if not isinstance(source_id, str) or not isinstance(quote, str):
            continue
        reasons = []
        task_exact = method.rank.planning.text(task_quote, 500) and any(task_quote in text for text in task)
        if not task_exact:
            reasons.append("TASK_QUOTE")
        if source_id not in memories:
            reasons.append("MEMORY_ID")
        elif not method.rank.grounded(source, {source_id: {"text": memories[source_id]}}):
            passages = method.rank.draft.user_source(memories[source_id])
            squeezed = "".join(quote.split())
            if quote.strip() and quote.strip() in memories[source_id]:
                reasons.append("OUTSIDE_USER_PASSAGE")
            elif squeezed and any(squeezed in "".join(text.split()) for text in passages):
                reasons.append("USER_QUOTE_WHITESPACE_ONLY")
            else:
                reasons.append("USER_QUOTE_NOT_FOUND")
        if reasons:
            resolutions.append({"effect": key, "source": source_id, "source_quote": quote,
                                "task_quote": task_quote, "reasons": reasons})
    return resolutions


def replay_draft_anchors(row, root, blocks, failures):
    """Test a narrower draft-span witness on rejected proposals, without grading it."""
    method = run.method
    body = method.rank.model_object(row["attempts"][method.STRUCTURAL]["raw"], "effects")
    eligible = {
        item["effect"] for item in failures
        if item["reasons"] == ["TASK_QUOTE"] and isinstance(item["task_quote"], str)
        and item["task_quote"].strip() and any(
            isinstance(edit, dict) and isinstance(edit.get("effects"), list)
            and item["effect"] in edit["effects"] and isinstance(edit.get("before"), str)
            and item["task_quote"] in edit["before"]
            for edit in body["edits"]
        )
    }
    draft_witnesses = {}
    for effect in body["effects"]:
        if (isinstance(effect, dict) and isinstance(effect.get("id"), str)
                and effect["id"] in eligible and effect.get("authority") != "DELEGATED"):
            draft_witnesses[effect["id"]] = effect["task_quote"]
            # Preserve the generated draft witness separately. The original task
            # quote is supplied here only to test the downstream original compiler.
            effect["task_quote"] = root["public_task"]["query"]
    if not draft_witnesses:
        return None
    effects, edits, _ = method.parse(root, blocks, json.dumps(body))
    answer, applied, _ = method.render(root, blocks, effects, edits, scope=True)
    if answer == row["outputs"][method.SCOPED]:
        return None
    return {"uid": row["uid"], "primary": row["primary"], "group": row["group"],
            "draft_witnesses": draft_witnesses, "applied": applied,
            "base_answer": row["outputs"][method.SCOPED], "answer": answer,
            "score_status": "NOT_SCORED_DIAGNOSTIC"}


def compare(rows, data, roots):
    method = run.method
    counts, source_uses, source_funnel = Counter(), Counter(), Counter()
    changes, mixed_edits, anchor_failures, anchor_replays = [], [], [], []
    for row in rows:
        uid, out = row["uid"], row["outputs"]
        layer = "primary" if row["primary"] else "regression"
        for arm, attempt in row["attempts"].items():
            counts[f"{layer}/{arm}/{attempt['status']}"] += 1
        if method.SCOPED not in out:
            continue
        root, task = roots[uid], data[uid]
        initial = method.rank.render(root, task["blocks"], {}, method.rank.DRAFT)["answer"]
        evidence = root["original_sources"]
        labels = row["labels"]
        if len(labels) != len(evidence) or any(item["memory_id"] != f"M{i}" for i, item in enumerate(evidence)):
            raise ValueError(f"Author positions cannot be aligned for {uid}")
        author_labels = {item["memory_id"]: label for item, label in zip(evidence, labels, strict=True)}
        counts[f"{layer}/compiled"] += 1
        counts.update(f"{layer}/contract/{reason}" for reason in row["rejected"])
        effects = row["effects"]
        proposal = method.rank.model_object(row["attempts"][method.STRUCTURAL]["raw"], "effects")
        proposed_sources = {item["source"]["id"] for item in proposal["effects"]
                            if isinstance(item, dict) and isinstance(item.get("source"), dict)
                            and isinstance(item["source"].get("id"), str)}
        parsed_sources = {effect["source"]["id"] for effect in effects.values()}
        linked_sources = {effects[key]["source"]["id"] for edit in row["proposed_edits"] for key in edit["effects"]}
        unscoped_sources = {effects[key]["source"]["id"] for edit in row["execution"][method.STRUCTURAL]["applied"]
                            for key in edit["effects"]}
        scoped_sources = {effects[key]["source"]["id"] for edit in row["execution"][method.SCOPED]["applied"]
                          for key in edit["effects"]}
        stages = (("proposed", proposed_sources), ("effect", parsed_sources), ("edit", linked_sources),
                  ("unscoped", unscoped_sources), ("scoped", scoped_sources))
        for source, label in author_labels.items():
            source_funnel[f"{layer}/{label}/available"] += 1
            for stage, selected_sources in stages:
                source_funnel[f"{layer}/{label}/{stage}"] += source in selected_sources
        if "EFFECT_ANCHOR" in row["rejected"]:
            failures = rejected_anchors(row, root)
            for failed in failures:
                anchor_failures.append({"uid": uid, "primary": row["primary"],
                                        "label": author_labels.get(failed["source"]), **failed})
                counts.update(f"{layer}/anchor/{reason}" for reason in failed["reasons"])
            restored = replay_draft_anchors(row, root, task["blocks"], failures)
            if restored:
                anchor_replays.append(restored)
        for item in row["execution"][method.SCOPED]["rejected"]:
            if item["reason"] != "ROLE_FORCE_SCOPE":
                continue
            edit = item["edit"]
            kept = [key for key in edit["effects"] if method.permitted(effects[key])]
            if not kept:
                continue
            excluded = [key for key in edit["effects"] if key not in kept]
            sources = {key: effects[key]["source"]["id"] for key in edit["effects"]}
            mixed_edits.append({"uid": uid, "group": row["group"], "primary": row["primary"],
                                "edit": edit, "permitted_effects": kept, "blocked_effects": excluded,
                                "sources": sources,
                                "permitted_author_labels": [author_labels[sources[key]] for key in kept],
                                "blocked_author_labels": [author_labels[sources[key]] for key in excluded]})
        for arm, selected in ((method.STRUCTURAL, unscoped_sources), (method.SCOPED, scoped_sources)):
            audit = row["execution"][arm]
            counts[f"{layer}/{arm}/changes_draft"] += out[arm] != initial
            for edit in audit["applied"]:
                kind = task["blocks"][edit["block"]]["kind"]
                counts[f"{layer}/{arm}/{kind}_edits"] += 1
            for item in audit["rejected"]:
                counts[f"{layer}/{arm}/rejected/{item['reason']}"] += 1
            for memory, label in zip(evidence, labels, strict=True):
                source_uses[f"{layer}/{arm}/{label}/available"] += 1
                source_uses[f"{layer}/{arm}/{label}/applied"] += memory["memory_id"] in selected
        if out[method.SCOPED] == out[method.STRUCTURAL]:
            if method.SCOPED in row["native"]:
                a, b = (row["native"][arm] for arm in (method.SCOPED, method.STRUCTURAL))
                if (a.get("request_sha256"), a["fields"]) != (b.get("request_sha256"), b["fields"]):
                    raise ValueError(f"Equal answers have unequal native receipts for {uid}")
            continue
        changes.append({"uid": uid, "primary": row["primary"], "group": row["group"],
                        "effects": effects, "execution": row["execution"], "outputs": out,
                        "native": {arm: cell["fields"] for arm, cell in row["native"].items()}})
    return {"counts": counts, "source_positions": source_uses, "source_funnel": source_funnel, "scope_changes": changes,
            "edits_with_mixed_role_admission": mixed_edits,
            "effect_anchor_failures": anchor_failures,
            "draft_anchor_replay": anchor_replays,
            "primary_changed_groups": len({case["group"] for case in changes if case["primary"]}),
            "new_requests": 0}


def deployment_cost(rows, ledger, inputs):
    """Compare actual reported usage on the very same scored primary histories."""
    _, _, _, roots, plan, older_compose = inputs
    author = run.prior.old.prior.parent.prior.parent.joint.prior.formal
    evaluation = run.read(author.OUT / "PLAN.json")
    drafts = run.task_only.saved_drafts(plan)
    replies = {digest: item[0] for digest, item in older_compose.items()}
    replies.update({r["request_sha256"]: r for r in ledger if r["unit"]["stage"] == run.STAGE})
    method = run.method
    arms = (method.SCOPED, method.ORDINARY, *run.prior.old.BASELINES)
    common = []
    for row in rows:
        if not row["primary"] or any("match" not in row["native"][arm]["fields"] for arm in arms):
            continue
        draft = numeric_cost(drafts[row["draft_origin"]]["record"]["usage"])
        if draft is None:
            continue
        usage = {}
        for arm, emitted in ((method.SCOPED, method.STRUCTURAL), (method.ORDINARY, method.ORDINARY)):
            record = replies[row["attempts"][emitted]["request_sha256"]]
            amount = numeric_cost(record["usage"])
            if amount is not None:
                usage[arm] = draft + amount
        for arm in run.prior.old.BASELINES:
            amount = old_cost(evaluation, roots[row["uid"]], arm)
            if amount is not None:
                usage[arm] = amount
        if all(arm in usage for arm in arms):
            common.append({"group": row["group"], "positions": row["positions"], "usage": usage,
                           "match": {arm: row["native"][arm]["fields"]["match"]["matched"] for arm in arms}})
    return {**profile(common, arms), "positions": sum(row["positions"] for row in common),
            "matched": {arm: sum(row["match"][arm] for row in common) for arm in arms},
            "includes_shared_task_draft": True, "includes_judge": False}


def draft_feasibility(rows):
    """Stratify observed FM by the archived draft score on common histories."""
    method = run.method
    arms = (run.prior.INITIAL, method.STRUCTURAL, method.SCOPED, method.ORDINARY)
    strata = defaultdict(list)
    for row in rows:
        if not row["primary"] or not set(row["labels"]) & {"B", "C"}:
            continue
        fm = {arm: row["native"][arm]["fields"].get("FM") for arm in arms}
        if any(not isinstance(value, (int, float)) for value in fm.values()):
            continue
        layer = "draft_FM_above_zero" if fm[run.prior.INITIAL] > 0 else "draft_FM_zero"
        strata[layer].append({"uid": row["uid"], "group": row["group"], "FM": fm})
    return {layer: {"cases": len(selected), "source_groups": len({r["group"] for r in selected}),
                    "FM_totals": {arm: sum(r["FM"][arm] for r in selected) for arm in arms},
                    "rows": selected}
            for layer, selected in strata.items()}


def judge_footprint(inputs, rows):
    """Count old exact receipts and shared new Judge wires without dispatch."""
    prior = run.prior
    exact = prior.old.prior.cache(inputs[4])[run.JUDGE]
    for directory in (prior.old.prior.OUT, prior.old.OUT, prior.OUT):
        exact.update(run.read(directory / f"{run.JUDGE}_EXACT.json"))
    new_digests, origins = set(), Counter()

    def count(_, jobs):
        response = {}
        for uid, arm, wire in jobs:
            digest = run.sha(wire)
            if digest in exact:
                origins["archived_exact"] += 1
            elif digest in new_digests:
                origins["same_answer_in_this_window"] += 1
            else:
                origins["new_request"] += 1
                new_digests.add(digest)
            response[uid, arm] = exact.get(digest, ({"status": "OFFLINE_NO_GRADE", "request_sha256": digest}, None))
        return response

    copies = {r["uid"]: {**r, "native": dict(r["native"])} for r in rows}
    run.grade(copies, count)
    return {"counts": origins, "logical": sum(origins.values()), "expected_physical": len(new_digests),
            "expected_request_hashes": sorted(new_digests), "new_requests": 0}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("live", "settled"))
    args = parser.parse_args()
    inputs = run.prepare()
    if args.mode == "settled":
        if run.read(run.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Run has not settled")
        settled = run.read(run.OUT / "SETTLED.json")
        rows = settled["rows"]
    else:
        rows = observed(inputs)
    report = compare(rows, inputs[2], inputs[3])
    report["score_reuse"] = judge_footprint(inputs, rows)
    if args.mode == "settled":
        grade_receipts = {r["request_sha256"] for r in settled["ledger"] if r["unit"]["stage"] == run.JUDGE}
        if grade_receipts != set(report["score_reuse"]["expected_request_hashes"]):
            raise ValueError("The executed Judge roster differs from reconstructed unique grading requests")
        report["primary_matched_deployment"] = deployment_cost(rows, settled["ledger"], inputs)
        report["draft_feasibility"] = draft_feasibility(rows)
    print(json.dumps(report, ensure_ascii=False, indent=2))
