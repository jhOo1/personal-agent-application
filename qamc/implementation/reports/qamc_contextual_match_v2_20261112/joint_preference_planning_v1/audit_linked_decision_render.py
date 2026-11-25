"""Replay decision-linked edits and their exposure without dispatching requests."""
from argparse import ArgumentParser
from collections import Counter
import json
from unittest.mock import patch

from deployment_cost import numeric_cost, old_cost, profile
import run_linked_decision_render as run


def observed(inputs):
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    receipts = run.probe.stage_receipts(run.COMPOSE)

    def snapshot(_, jobs):
        result = {}
        for uid, arm, wire in jobs:
            record, body = receipts[uid, arm]
            result[uid, arm] = (record, body) if record else (
                {"status": "UNISSUED", "request_sha256": run.sha(wire)}, None
            )
        return result

    return list(run.generate(inputs, snapshot).values())


def compare(rows, source, roots):
    method = run.method
    counts = Counter()
    by_label = Counter()
    changes, rejected_guards, hidden_replacements = [], [], []
    for row in rows:
        uid, out = row["uid"], row["outputs"]
        layer = "primary" if row["primary"] else "regression"
        for arm, attempt in row["attempts"].items():
            counts[f"{layer}/{arm}/{attempt['status']}"] += 1
        if method.ON not in out:
            continue
        policy, links = row["policy"], row["links"]
        active = {slot for slot, rec in policy.items() if rec["guard"]}
        blocks = source[uid]["execution"]["blocks"]
        off = method.render(roots[uid], blocks, policy, {})
        on = method.render(roots[uid], blocks, policy, links)
        if off["answer"] != out[method.OFF] or on["answer"] != out[method.ON] or off["decisions"] != on["decisions"]:
            raise ValueError(f"Link toggle changed a recommendation block or replay differs on {uid}")
        counts[f"{layer}/has_guard"] += bool(active)
        counts[f"{layer}/all_cases_with_links"] += bool(links)
        counts.update(f"{layer}/rejected/{reason}" for reason in row["rejected"])
        for slot in sorted(active):
            replacements = policy[slot]["guard"]["replacements"]
            if not replacements:
                continue
            visible = on["decisions"][slot]["shown"]
            if not any(key.startswith("G") for key in visible):
                hidden_replacements.append({"uid": uid, "primary": row["primary"], "slot": slot,
                                            "shown": visible, "proposed_replacements": replacements})
        guarded_ids = {record["id"] for slot in active for record in policy[slot]["guard"]["sources"]}
        linked_choices = {edit["choice"] for edits in links.values() for edit in edits}
        linked_ids = {record["id"] for slot in linked_choices for record in policy[slot]["guard"]["sources"]}
        evidence = roots[uid]["original_sources"]
        labels = row["labels"]
        if len(labels) != len(evidence) or any(item["memory_id"] != f"M{i}" for i, item in enumerate(evidence)):
            raise ValueError(f"Unexpected author label alignment for {uid}")
        for memory, label in zip(evidence, labels, strict=True):
            evidence_id = memory["memory_id"]
            by_label[f"{layer}/{label}/available"] += 1
            by_label[f"{layer}/{label}/guarded"] += evidence_id in guarded_ids
            by_label[f"{layer}/{label}/linked"] += evidence_id in linked_ids
        if "GUARD" in row["rejected"]:
            proposed = method.rank.model_object(row["attempts"][method.OFF]["raw"], "decisions")
            memories = {item["memory_id"]: item for item in evidence}
            for decision in proposed["decisions"]:
                if not isinstance(decision, dict) or not isinstance(decision.get("block"), str):
                    continue
                slot, guard = decision["block"], decision.get("guard")
                block = blocks.get(slot, {})
                if not isinstance(guard, dict) or block.get("kind") != "CHOICE":
                    continue
                options = {f"O{i}" for i in range(1, len(block["lines"]) + 1)}
                affected = block["affected"]
                if method.rank.valid_guard(guard, affected, options, memories):
                    continue
                accepted_roles = [
                    role for role in sorted(method.rank.RELATIONS)
                    if method.rank.valid_guard(guard, role, options, memories)
                ]
                rejected_guards.append({"uid": uid, "primary": row["primary"], "slot": slot,
                                        "affected": affected, "guard": guard,
                                        "accepted_if_draft_role_changed": accepted_roles})
        if off["answer"] == on["answer"]:
            continue
        counts[f"{layer}/answer_changed"] += 1
        changes.append({
            "uid": uid, "group": row["group"], "primary": row["primary"], "condition": row["condition"],
            "links": links, "guards": {slot: policy[slot]["guard"] for slot in sorted(active)},
            "baseline": off["answer"], "candidate": on["answer"], "ordinary": out.get(method.ORDINARY),
            "native": {arm: row["native"][arm]["fields"] for arm in (*method.MODES, *run.CONTROLS)
                       if arm in row["native"]},
        })
    return {"counts": counts, "author_label_exposure": by_label, "changes": changes,
            "rejected_guard_role_probe": rejected_guards,
            "replacement_not_displayed": hidden_replacements,
            "primary_changed_source_groups": len({r["group"] for r in changes if r["primary"]}),
            "new_model_requests": 0}


def matched_cost(rows, ledger, source, roots):
    old = run.old
    method = run.method
    formal = old.prior.parent.prior.parent.joint.prior.formal
    reference = run.read(formal.OUT / "PLAN.json")
    draft_cache = run.read(old.prior.OUT / f"{old.TASK}_EXACT.json")
    draft_cache.update(run.read(old.OUT / f"{old.TASK}_EXACT.json"))
    receipts = {r["request_sha256"]: r for r in ledger if r["unit"]["stage"] == run.COMPOSE}
    methods = (method.ON, method.ORDINARY, *old.BASELINES)
    common = []
    for row in rows:
        if not row["primary"] or any("match" not in row["native"][arm]["fields"] for arm in methods):
            continue
        uid = row["uid"]
        parent = source[uid]["execution"]
        draft = numeric_cost(draft_cache[parent["task_sha256"]][0]["usage"])
        if draft is None:
            continue
        usage = {}
        for arm, physical in ((method.ON, method.OFF), (method.ORDINARY, method.ORDINARY)):
            receipt = receipts[row["attempts"][physical]["request_sha256"]]
            amount = numeric_cost(receipt["usage"])
            if amount is not None:
                usage[arm] = draft + amount
        for arm in old.BASELINES:
            amount = old_cost(reference, roots[uid], arm)
            if amount is not None:
                usage[arm] = amount
        if all(arm in usage for arm in methods):
            common.append({"group": row["group"], "positions": row["positions"], "usage": usage,
                           "matched": {arm: row["native"][arm]["fields"]["match"]["matched"] for arm in methods}})
    return {**profile(common, methods), "positions": sum(row["positions"] for row in common),
            "matches": {arm: sum(row["matched"][arm] for row in common) for arm in methods},
            "excludes_judge_usage": True, "includes_initial_task_only_draft": True}


def replay_content_only(rows, source, roots):
    """Isolate the CHOICE gate offline, with the model's predicted audience left unverified."""
    method = run.method
    affected = {"SELF": "SELF", "PARTICIPANT": "SHARED", "GROUP": "SHARED"}
    changed = []
    for row in rows:
        uid = row["uid"]
        root = roots[uid]
        blocks = source[uid]["execution"]["blocks"]
        if method.ON not in row["outputs"] or any(b["kind"] == "CHOICE" for b in blocks.values()):
            continue
        raw = row["attempts"][method.OFF]["raw"]
        proposed = method.rank.model_object(raw, "decisions")
        sources = {item["memory_id"]: item for item in root["original_sources"]}
        provisional = {}
        for decision in proposed["decisions"]:
            if not isinstance(decision, dict) or not isinstance(decision.get("block"), str):
                continue
            slot, guard = decision["block"], decision.get("guard")
            if slot not in blocks or not isinstance(guard, dict) or not isinstance(guard.get("audience"), str):
                continue
            # Selection operations cannot act on prose. Only evaluate the proposed text links.
            guard = {**guard, "exclude": [], "replacements": []}
            if method.rank.valid_guard(guard, affected.get(guard["audience"]), set(), sources):
                provisional[slot] = {"guard": guard, "preferences": []}
        if not provisional:
            continue
        with patch.object(method.rank, "read_policy", return_value=(provisional, [])):
            policy, links, rejected = method.compile_links(root, blocks, raw)
        answer = method.render(root, blocks, policy, links)["answer"]
        if answer != row["outputs"][method.ON]:
            changed.append({"uid": uid, "group": row["group"], "primary": row["primary"],
                            "provisional_guards": provisional, "links": links, "rejected": rejected,
                            "answer": answer, "score_status": "NOT_SCORED_DIAGNOSTIC"})
    return {"changed": changed, "new_model_requests": 0}


def effect_on_scores(rows):
    """Split the native toggle difference by whether the intervention changed the answer."""
    method = run.method
    partition = {}
    for row in rows:
        out, native = row["outputs"], row["native"]
        if method.ON not in out:
            continue
        off, on = (native[arm] for arm in (method.OFF, method.ON))
        changed = out[method.OFF] != out[method.ON]
        if not changed and (on["fields"] != off["fields"] or on["request_sha256"] != off["request_sha256"]):
            raise ValueError(f"Identical answers have different native receipts on {row['uid']}")
        layer = "primary" if row["primary"] else "regression"
        partition.setdefault((layer, changed), []).append(row)

    rows_by_partition = []
    for (layer, changed), group in sorted(partition.items()):
        compare = run.old.prior.parent.prior.parent.joint.parent.comparisons.grade_pair
        summary = {
            "layer": layer, "answer_changed": changed, "cases": len(group),
            "source_groups": len({r["group"] for r in group}),
        }
        match = run.replay.paired(group, method.OFF, method.ON)
        summary["match"] = {k: match.get(k) for k in ("valid_cases", "scores", "match_delta")}
        for field in ("FM", "UPB", "OPB", "VG", "full_match"):
            comparison = compare(group, method.OFF, method.ON, field)
            summary[field] = {k: comparison.get(k) for k in ("n", "left", "right", "delta")}
        rows_by_partition.append(summary)
    return rows_by_partition


def accepted_guard_gap(rows):
    """Locate the remaining B/C gap by the actual point of guard activation."""
    method = run.method
    buckets = {"NO_ACCEPTED_GUARD": [], "GUARD_WITHOUT_EDIT": [], "EDITED": []}
    for row in rows:
        if not (row["primary"] and row["eligible"] and set(row["labels"]) & {"B", "C"}):
            continue
        policy = row.get("policy", {})
        if row.get("links"):
            buckets["EDITED"].append(row)
        elif any(record["guard"] for record in policy.values()):
            buckets["GUARD_WITHOUT_EDIT"].append(row)
        else:
            buckets["NO_ACCEPTED_GUARD"].append(row)
    compare = run.old.prior.parent.prior.parent.joint.parent.comparisons.grade_pair
    result = {}
    for key, bucket in buckets.items():
        entry = {"uids": [row["uid"] for row in bucket], "comparisons": {}}
        for arm in (method.ORDINARY, *run.old.BASELINES):
            fields = {}
            for field in ("FM", "UPB", "OPB"):
                cell = compare(bucket, arm, method.ON, field)
                n = cell["n"]
                fields[field] = {"n": n, "severity_delta_total": round(n * cell["delta"], 8) if n else None}
            entry["comparisons"][arm] = fields
        result[key] = entry
    return result


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("live", "settled"))
    args = parser.parse_args()
    prepared = run.prepare()
    if args.mode == "settled":
        if run.read(run.OUT / "RUN_STATE.json")["state"] != "COMPLETE":
            raise ValueError("Run has not settled")
        settlement = run.read(run.OUT / "SETTLED.json")
        rows = settlement["rows"]
    else:
        rows = observed(prepared)
    result = compare(rows, prepared[2], prepared[3])
    result["content_only_replay"] = replay_content_only(rows, prepared[2], prepared[3])
    if args.mode == "settled":
        result["primary_matched_cost"] = matched_cost(rows, settlement["ledger"], prepared[2], prepared[3])
        result["paired_by_answer_change"] = effect_on_scores(rows)
        result["accepted_guard_gap"] = accepted_guard_gap(rows)
    print(json.dumps(result, ensure_ascii=False, indent=2))
