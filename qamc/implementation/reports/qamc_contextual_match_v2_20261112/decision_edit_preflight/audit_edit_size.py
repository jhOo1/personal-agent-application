"""Audit how shared size limits act on saved editor replies, without scoring variants."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_decision_edit as run


def trim_span(draft, start, end, replacement):
    original = draft[start:end]
    prefix = 0
    for a, b in zip(original, replacement):
        if a != b:
            break
        prefix += 1
    suffix = 0
    for a, b in zip(reversed(original[prefix:]), reversed(replacement[prefix:])):
        if a != b:
            break
        suffix += 1
    return start + prefix, end - suffix, replacement[prefix:len(replacement) - suffix]


def render(draft, spans):
    text = []
    cursor = 0
    for start, end, replacement in spans:
        if start < cursor:
            raise ValueError("Cannot reconstruct overlapping edits")
        text.extend((draft[cursor:start], replacement))
        cursor = end
    return "".join((*text, draft[cursor:]))


def sizes(spans):
    return {"removed": sum(end - start for start, end, _ in spans),
            "inserted": sum(len(replacement) for _, _, replacement in spans)}


def oversized(value, draft):
    return value["removed"] > len(draft) // 2 or value["inserted"] > max(256, len(draft) // 2)


def audit_reply(record, raw, payload, labels):
    item = run.parse_edit(record, raw, payload, record["request_sha256"])
    if item["status"] != "OK":
        return {"status": item["status"], "references": None}
    draft = payload["original_answer"]
    task = tuple(run.edit.task_text(payload["task"]))
    sources = run.edit.source_index(payload["source_evidence"])
    edits = json.loads(raw, object_pairs_hook=run.edit.unique_keys)["edits"]
    valid = []
    used = Counter()
    proposed_ids, anchored_ids, applied_ids = set(), set(), set()
    for index, operation in enumerate(edits):
        source = operation.get("memory") if isinstance(operation, dict) else None
        claimed = source.get("id") if isinstance(source, dict) else None
        mid = claimed if isinstance(claimed, str) and claimed in sources else None
        if mid is not None:
            proposed_ids.add(mid)
        reason, span = run.edit.span(operation, draft, task, sources)
        if reason is None:
            valid.append(span)
            used[labels[mid] if mid is not None else "TASK"] += 1
            if mid is not None:
                anchored_ids.add(mid)
        if index in item["applied"] and mid is not None:
            applied_ids.add(mid)
    if not applied_ids <= anchored_ids <= proposed_ids:
        raise ValueError("Compiler applied a memory edit outside the validated proposal")
    valid.sort()
    result = {"status": item["transaction"], "draft_chars": len(draft), "proposed": len(edits),
              "accepted_spans_before_size_check": len(valid), "source_labels_for_audit": used,
              "references": {
                  "author_positions": Counter(labels.values()),
                  "proposed": Counter(labels[mid] for mid in proposed_ids),
                  "anchored": Counter(labels[mid] for mid in anchored_ids),
                  "applied": Counter(labels[mid] for mid in applied_ids),
                  "final_answer_sha256": sha(item["answer"]),
              }}
    if item["transaction"] == "overlapping_spans":
        return result
    clipped = [trim_span(draft, *span) for span in valid]
    proposed, trimmed = render(draft, valid), render(draft, clipped)
    if proposed != trimmed:
        raise ValueError("Trimming unchanged edges changed the answer bytes")
    before, after = sizes(valid), sizes(clipped)
    if oversized(before, draft) != (item["transaction"] == "edit_budget"):
        raise ValueError("Size reconstruction disagrees with frozen compiler")
    if item["transaction"] != "edit_budget" and item["answer"] != proposed:
        raise ValueError("Rebuilt answer differs from frozen compiler output")
    return {**result, "original_size_accounting": before, "trimmed_size_accounting": after,
            "budget_rejected_only_untrimmed": item["transaction"] == "edit_budget" and not oversized(after, draft),
            "proposed_answer_sha256_diagnostic_only": sha(proposed)}


def matched_references(rows):
    by_uid = defaultdict(dict)
    for row in rows:
        if row["references"] is not None:
            by_uid[row["uid"]][row["method"]] = row
    paired = [pair for pair in by_uid.values() if set(pair) == set(run.edit.METHODS)]
    panels = {"all": paired}
    for scope in ("all_A", "contains_B", "contains_C"):
        panels[scope] = [pair for pair in paired if pair[run.GENERIC]["stratum"] == scope]
    result = {}
    for scope, pairs in panels.items():
        arms = {}
        for method in run.edit.METHODS:
            totals = {key: Counter() for key in ("author_positions", "proposed", "anchored", "applied")}
            statuses = Counter()
            for pair in pairs:
                row = pair[method]
                statuses[row["status"]] += 1
                for key, counter in totals.items():
                    counter.update(row["references"][key])
            arms[method] = {"status": statuses, **totals}
        result[scope] = {
            "roots": len(pairs), "source_groups": len({pair[run.GENERIC]["group"] for pair in pairs}),
            "different_visible_answers": sum(
                len({row["references"]["final_answer_sha256"] for row in pair.values()}) == 2 for pair in pairs),
            "arms": arms,
        }
    return result


def run_audit():
    frozen = run.read(run.OUT / "FROZEN.json")
    plan, roots, payloads, jobs = run.prepare(frozen["service_reference_sha256"])
    if plan != frozen:
        raise ValueError("Frozen study changed")
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    receipts = {rec["request_sha256"]: (rec, raw) for rec, raw in run.probe.stage_receipts(run.EDIT).values() if rec}
    archived = {row["uid"]: row for row in run.read(run.comparisons.run.OUT / "COMPLETED.json")["rows"]}
    by_uid = {r["uid"]: r for r in roots}
    by_stratum, rows = defaultdict(Counter), []
    for uid, method, wire in jobs:
        digest = sha(wire)
        seen = receipts.get(digest)
        if not seen or seen[0]["status"] != "OK" or seen[1] is None:
            continue
        labels = archived[uid]["labels"]
        sources = payloads[uid]["source_evidence"]
        mapping = dict(zip((r["memory_id"] for r in sources), labels, strict=True))
        stratum = "contains_C" if "C" in labels else "contains_B" if "B" in labels else "all_A"
        details = audit_reply(*seen, payloads[uid], mapping)
        for name in (stratum, "all"):
            by_stratum[method + "/" + name].update([details["status"]])
            if details.get("budget_rejected_only_untrimmed"):
                by_stratum[method + "/" + name]["budget_rejected_only_untrimmed"] += 1
        rows.append({"uid": uid, "method": method, "group": by_uid[uid]["group"], "stratum": stratum,
                     "request_sha256": digest, **details})
    return {
        "state": run.read(run.OUT / "RUN_STATE.json")["state"],
        "physical_editor_records_observed": len(receipts),
        "usable_assigned_cases": plan["eligible"], "logical_visible_replies_audited": len(rows),
        "by_stratum": dict(sorted(by_stratum.items())), "paired_source_references": matched_references(rows),
        "rows": rows,
        "new_model_requests": 0, "new_method_scores": 0,
        "diagnostic": "Trimming removes only unchanged contiguous edges after verifying the exact original anchor. "
                      "It retains the full intended draft bytes and does not validate whether the changes are appropriate. "
                      "No frozen result or request is changed.",
    }


if __name__ == "__main__":
    print(json.dumps(run_audit(), ensure_ascii=False, indent=2))
