"""Rebuild the evaluated editor inputs and check receipts without sending requests."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json
import re

from qamc.common import canonical, parse_object, sha, token_estimate

import run_main_answer_revision as run


def verify_receipts(stage, expected):
    path = run.OUT / f"{stage}_MANIFEST.json"
    if not path.exists():
        if stage == run.EDITOR:
            raise ValueError("Missing editor manifest")
        return {}
    data = run.read(path)
    protocol = data["protocol"]
    seen = {}
    for entry in data["units"]:
        unit, wire = entry["unit"], entry["request"]
        digest = sha(wire)
        if digest in seen or unit["stage"] != stage or unit["protocol_sha256"] != sha(protocol):
            raise ValueError(f"Duplicate or unbound {stage} request")
        seen[digest] = (unit["root_id"], unit["method"])
    if seen != expected:
        raise ValueError(f"{stage} allocation disagrees with the selected panel")
    published = run.probe.stage_receipts(stage)
    reference = run.read(run.OUT / "FROZEN.json")["service_reference_sha256"]
    actual = {}
    for digest, key in seen.items():
        rec, raw = published[key]
        if rec is not None:
            if (rec["request_sha256"] != digest or rec["automatic_retries"] != 0
                    or rec["reference_config_sha256"] != reference):
                raise ValueError(f"Receipt differs from the frozen configuration: {key}")
            actual[key] = rec, raw
    return actual


def explain_rejection(raw, draft, status, finish_reason):
    """Diagnose saved failures without applying a replacement or inventing an anchor."""
    result = {"status": status, "finish_reason": finish_reason, "returned_characters": len(raw or "")}
    if status == "UNRESOLVED_DRAFT_ANCHOR":
        anchors = Counter()
        for operation in json.loads(raw)["edits"]:
            before = operation.get("before") if isinstance(operation, dict) else None
            if not isinstance(before, str) or not before.strip():
                anchors["invalid_later_operation"] += 1
                continue
            start = draft.find(before)
            if start < 0:
                plain = before.replace("**", "")
                matches = [line for line in draft.splitlines()
                           if "**" in line and plain and plain in line.replace("**", "")]
                anchors["same_line_ignoring_strong_markers" if len(matches) == 1
                        else "no_unique_match_ignoring_strong_markers"] += 1
            elif draft.find(before, start + 1) >= 0:
                anchors["ambiguous_original_text"] += 1
            else:
                anchors["exact_original_text"] += 1
        result["anchor_observations"] = anchors
    elif status == "INVALID_REVISION_JSON":
        value = (raw or "").lstrip()
        result["surface"] = ("json_fence" if re.match(r"```(?:json)?\s*\{", value) else "object_like"
                             if value.startswith("{") else "other_text" if value else "empty")
    return result


def editor_audit(spec, jobs, old, archive):
    """Confirm draft, task, source order and role licenses directly against their archives."""
    _, rows, _ = run.checked()
    actors = {row["uid"]: row for row in rows}
    public = {root["uid"]: root for root in archive["roots"]}
    baseline = {row["uid"]: row for row in old}
    expected = {}
    for uid, arm, wire in jobs:
        expected.setdefault(sha(wire), (uid, arm))
    receipts = verify_receipts(run.EDITOR, expected)
    inputs, details, revised = {}, {}, {}
    issued, shared_delta, reported_delta = Counter(), [], []
    strata = defaultdict(Counter)
    references, rejections = {}, []
    for uid, arm, wire in jobs:
        pkt = json.loads(wire["messages"][1]["content"])
        root, saved = public[uid], actors[uid]
        actor = saved["actor"][run.edit.realization.SEGMENTED]
        selection = saved["selection"]
        draft = parse_object(actor["raw"])["main_answer"] if selection["route"] == "SEGMENTED" else actor["answer"]
        uses = [edge for edge in selection["uses"] if edge["use"] in ("GUARD", "STYLE_OR_CONTENT")]
        wanted = {edge["memory_id"] for edge in uses}
        source = [item for item in root["original_sources"] if item["memory_id"] in wanted]
        if (pkt != {"task": root["public_task"], "draft": draft, "licenses": uses, "source_evidence": source}
                or sha(draft) != spec["draft_sha256"][uid] or sha(wire) != spec["wire_sha256"][f"{uid}/{arm}"]):
            raise ValueError(f"Editor input drift: {uid}/{arm}")
        if uid in inputs:
            prior = inputs[uid]
            if prior["messages"][1:] != wire["messages"][1:] or prior["messages"][0] == wire["messages"][0]:
                raise ValueError(f"Unequal evidence or controls: {uid}")
            shared_delta.append(token_estimate(canonical(wire["messages"])) - token_estimate(canonical(prior["messages"])))
            records = [receipts.get(expected[sha(candidate)], (None, None))[0] for candidate in (prior, wire)]
            if all(rec and rec["status"] == "OK" for rec in records):
                counts = [(rec.get("usage") or {}).get("prompt_tokens") for rec in records]
                if all(isinstance(size, int) for size in counts):
                    reported_delta.append(counts[1] - counts[0])
        else:
            inputs[uid] = wire

        labels = dict(zip((item["memory_id"] for item in root["original_sources"]),
                          baseline[uid]["labels"], strict=True))
        if set(labels.values()) - {"A", "B", "C"} or len(labels) != len(root["original_sources"]):
            raise ValueError(f"Audit labels do not align with the frozen source IDs: {uid}")
        root_stratum = "all_A" if set(labels.values()) == {"A"} else "contains_BC"
        group = strata[arm, root_stratum]
        group["assigned"] += 1
        for label, count in Counter(labels[mid] for mid in wanted).items():
            group[f"licensed_source_positions_{label}"] += count
        rec, raw = receipts.get(expected[sha(wire)], (None, None))
        status = rec["status"] if rec is not None else "NOT_DISPATCHED"
        issued[arm, status] += 1
        if status != "OK":
            continue
        result = run.edit.apply(pkt, raw)
        group[result["status"]] += 1
        if result["answer"] == draft:
            group["original_answer_reusable"] += 1
        if result["status"] not in ("APPLIED", "NOOP"):
            rejections.append({"uid": uid, "method": arm, **explain_rejection(
                raw, draft, result["status"], rec.get("finish_reason"))})
        if result["status"] == "APPLIED":
            affected = {mid for op in result["applied"] for mid in op["sources"]}
            groups = {edge["use"] for edge in uses if edge["memory_id"] in affected}
            for kind in groups:
                group[f"touches_{kind}"] += 1
            group["patches"] += len(result["applied"])
            group["characters_removed"] += result["characters"]["removed"]
            group["characters_inserted"] += result["characters"]["inserted"]
            label_counts = Counter(labels[mid] for mid in affected)
            group["applied_citation_" + "".join(sorted(label_counts))] += 1
            for label, count in label_counts.items():
                group[f"edited_source_positions_{label}"] += count
            references[uid, arm] = label_counts
            revised[uid, arm] = result["answer"]
        details[uid, arm] = result

    paired_changes, paired_reference_shifts = Counter(), Counter()
    paired_root_changes = defaultdict(Counter)
    unilateral_detail = Counter()
    for uid in inputs:
        left, right = (details.get((uid, arm)) for arm in run.edit.ARMS)
        if left is None or right is None:
            continue
        changed_left, changed_right = (result["status"] == "APPLIED" for result in (left, right))
        if changed_left and changed_right:
            outcome = "same_revision" if left["answer"] == right["answer"] else "different_revisions"
        elif changed_left or changed_right:
            outcome = "generic_only" if changed_left else "decision_only"
            unchanged = right if changed_left else left
            unilateral_detail[f"{outcome}/{unchanged['status']}"] += 1
        else:
            outcome = "original_in_both"
        paired_changes[outcome] += 1
        root_stratum = "all_A" if set(baseline[uid]["labels"]) == {"A"} else "contains_BC"
        paired_root_changes[root_stratum][outcome] += 1
        if changed_left or changed_right:
            left_refs, right_refs = (references.get((uid, arm), {}) for arm in run.edit.ARMS)
            sl, sr = ("".join(sorted(bundle)) or "unchanged" for bundle in (left_refs, right_refs))
            paired_reference_shifts[f"{sl}->{sr}"] += 1
    return receipts, details, revised, {
        "editor_request_hashes_checked": len(expected), "identical_payload_pairs": len(inputs),
        "logical_editor_units": len(jobs), "physical_editor_reuse_slots": len(jobs) - len(expected),
        "estimated_prompt_delta_tokens": {"min": min(shared_delta), "max": max(shared_delta)},
        "reported_prompt_delta_tokens": ({"pairs": len(reported_delta), "min": min(reported_delta),
                                          "max": max(reported_delta)} if reported_delta else None),
        "editor_transport_by_method": {"/".join(key): count for key, count in issued.items()},
        "successful_editor_responses": {"/".join(key): count for key, count in strata.items()},
        "paired_revision_changes": paired_changes,
        "paired_revision_changes_by_root": paired_root_changes,
        "unilateral_change_other_arm_status": unilateral_detail,
        "compiler_rejections": rejections,
        "paired_edit_reference_label_sets": paired_reference_shifts,
        "label_audit_note": "Labels are joined after returning editor receipts. A citation identifies the proposed "
                            "basis for a patch, not whether the resulting answer overuses or underuses it.",
        "new_requests": 0,
    }


def grading_allocation(compiled, revised, spec, archive):
    """Build the expected native Judge allocation, without opening a model connection."""
    prior = run.grade_cache(archive)
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    plan = run.read(run.joint.prior.formal.OUT / "PLAN.json")
    author = run.joint.prior.author_cases(plan)
    graded = {key: sha(run.joint.parent.grade_request(plan, author[key[0]], answer))
              for key, answer in revised.items()}
    expected = {}
    for key, digest in graded.items():
        if digest not in prior:
            expected.setdefault(digest, key)
    by_arm = defaultdict(Counter)
    for (uid, arm), item in compiled.items():
        key = uid, arm
        if key not in graded:
            kind = "unchanged_draft_compiler_fallback" if item["status"] != "NOOP" else "unchanged_draft_model_noop"
        elif graded[key] in prior:
            kind = "exact_prior_judge_reuse"
        elif expected[graded[key]] != key:
            kind = "same_batch_judge_reuse"
        else:
            kind = "distinct_new_judge_wire"
        by_arm[arm][kind] += 1
    return graded, expected, prior, {
        "compiled_rows": len(compiled), "changed_answers": len(graded), "new_judge_wires": len(expected),
        "reuse_or_dispatch_by_arm": by_arm,
        "unchanged_without_license": 2 * sum(status == "NO_MAIN_LICENSE" for status in spec["non_dispatch"].values()),
    }


def terminal(spec, editor, compiled, revised, old, archive):
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("The experiment is not terminal")
    graded, expected, prior, _ = grading_allocation(compiled, revised, spec, archive)
    receipts = verify_receipts(run.JUDGE, expected)
    ledger = {(rec[0]["unit"]["stage"], rec[0]["request_sha256"]): rec[0]
              for rec in (*editor.values(), *receipts.values())}
    settled = run.read(run.OUT / "SETTLED.json")
    stored = {(rec["unit"]["stage"], rec["request_sha256"]): rec for rec in settled["ledger"]}
    if (ledger != stored or len(stored) != len(settled["ledger"])
            or len(ledger) != state["physical_requests"] or len(receipts) != len(expected)
            or any(rec["status"] == "PENDING_DELIVERY_UNKNOWN" for rec in ledger.values())):
        raise ValueError("Terminal ledger does not match the retained request receipts")

    reuse = Counter()
    for saved, reference in zip(settled["rows"], old, strict=True):
        uid = saved["uid"]
        if (uid != reference["uid"]
                or any(saved["native"][name] != value for name, value in reference["native"].items())):
            raise ValueError("Inherited native scores were modified")
        for arm in run.edit.ARMS:
            key = uid, arm
            detail, observation = saved["revisions"][arm], saved["native"][arm]
            if key in compiled and any(detail[name] != value for name, value in compiled[key].items()):
                raise ValueError(f"Saved revision differs from deterministic application: {key}")
            if key in graded:
                digest = graded[key]
                rec, raw = prior[digest] if digest in prior else receipts[expected[digest]]
                if (detail["judge_sha256"] != digest
                        or observation != run.joint.parent.parse_grade(rec, raw, saved["positions"])):
                    raise ValueError(f"Saved score differs from the native receipt: {key}")
                reuse["prior_exact_judge"] += digest in prior
                reuse["same_batch_judge"] += digest not in prior and expected[digest] != key
            elif key in compiled or spec["non_dispatch"].get(uid) == "NO_MAIN_LICENSE":
                if observation != {**reference["native"][run.MAIN], "reuse": run.MAIN}:
                    raise ValueError(f"An unchanged answer was not reuse scored: {key}")
                reuse["original_answer"] += 1
            elif observation["fields"]:
                raise ValueError(f"A missing revision acquired a native score: {key}")
    return {"terminal": True, "physical_receipts_verified": len(ledger), "physical_native_scores": len(receipts),
            "logical_changed_answers": len(revised), "reused_scores": reuse}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("editors", "grading", "terminal"))
    phase = parser.parse_args().phase
    plan, jobs, _, old, archive = run.prepare()
    if plan != run.read(run.OUT / "FROZEN.json"):
        raise ValueError("Frozen inputs have changed")
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    records, compiled, changed, audit = editor_audit(plan, jobs, old, archive)
    if phase == "grading":
        _, expected, _, grading = grading_allocation(compiled, changed, plan, archive)
        editors_settled = len(records) == audit["editor_request_hashes_checked"] and all(
            row["status"] != "PENDING_DELIVERY_UNKNOWN" for row, _ in records.values())
        judge_manifest = (run.OUT / f"{run.JUDGE}_MANIFEST.json").exists()
        can_verify = judge_manifest and editors_settled
        judged = verify_receipts(run.JUDGE, expected) if can_verify else {}
        audit["grading_allocation"] = {**grading, "editor_scope_complete": editors_settled,
                                       "published_judge_manifest_matches": True if can_verify else None,
                                       "judge_receipts": Counter(rec["status"] for rec, _ in judged.values())}
    elif phase == "terminal":
        audit.update(terminal(plan, records, compiled, changed, old, archive))
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
