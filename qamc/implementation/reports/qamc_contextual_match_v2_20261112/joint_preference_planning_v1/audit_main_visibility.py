"""Verify the in-flight RPEval exposure edit and the complete native score matrix."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_main_visibility as run


def exposure():
    plan, archive, jobs, _ = run.prepare()
    if run.read(run.OUT / "FROZEN.json") != plan:
        raise ValueError("Frozen exposure plan changed")
    history = {root["uid"]: root for root in archive["roots"]}
    _, originals, _ = run.checked()
    observations = {row["uid"]: row for row in originals}
    if set(history) != set(observations):
        raise ValueError("Raw memory roster differs from the archived trial")
    by_wire = defaultdict(list)
    counts, removed, retained = Counter(), Counter(), Counter()
    for uid, arm, wire in jobs:
        root, row = history[uid], observations[uid]
        digest = sha(wire)
        by_wire[digest].append(uid)
        audit = plan["intervention_roots"][uid]
        view = json.loads(wire["messages"][1]["content"])
        visible_ids = [r["memory_id"] for r in view["source_evidence"]]
        kept_ids = [edge["memory_id"] for edge in audit["kept"]]
        if digest != audit["after_sha256"] or view["task"] != root["public_task"] or visible_ids != kept_ids:
            raise ValueError("Masked Actor received evidence outside the frozen treatment")
        old = {e["memory_id"]: e for e in row["selection"]["uses"]}
        if set(old) != set(kept_ids) | set(audit["removed"]) or set(kept_ids) & set(audit["removed"]):
            raise ValueError("The treatment did not partition the original licensed evidence")
        labels = dict(zip((s["memory_id"] for s in root["original_sources"]), row["labels"], strict=True))
        counts["with_retained_evidence"] += bool(kept_ids)
        counts["with_removed_author_B_or_C"] += any(labels[mid] != "A" for mid in audit["removed"])
        counts["with_removed_author_C"] += any(labels[mid] == "C" for mid in audit["removed"])
        for mid, edge in old.items():
            target = retained if mid in kept_ids else removed
            target[edge["use"], labels[mid]] += 1
    manifest = run.read(run.OUT / f"{run.ACTOR}_MANIFEST.json")
    sent = {sha(unit["request"]): unit["unit"]["root_id"] for unit in manifest["units"]}
    if len(sent) != len(manifest["units"]) or sent.keys() != by_wire.keys():
        raise ValueError("Physical Actor manifest differs from the frozen deduplicated wires")
    if any(uid != by_wire[digest][0] for digest, uid in sent.items()):
        raise ValueError("A shared physical Actor wire has an unexpected representative")
    duplicates = [uids for uids in by_wire.values() if len(uids) > 1]
    spanning = [uids for uids in duplicates if len({plan["intervention_roots"][uid]["group"] for uid in uids}) > 1]
    report = {
        "logical_requests": len(jobs), "physical_manifest_requests": len(sent), "roots": dict(counts),
        "duplicate_request_groups": duplicates, "duplicate_requests_spanning_source_groups": spanning,
        "source_groups": len({v["group"] for v in plan["intervention_roots"].values()}),
        "removed_use_by_author_label": {"/".join(k): n for k, n in sorted(removed.items())},
        "retained_use_by_author_label": {"/".join(k): n for k, n in sorted(retained.items())},
        "expected_input_tokens_removed_per_logical_request": round(
            sum(v["estimated_input_tokens_removed"] for v in plan["intervention_roots"].values()) / len(jobs), 2),
        "new_model_calls": 0,
    }
    return plan, report


def complete(plan):
    state = run.read(run.OUT / "RUN_STATE.json")
    if state["state"] != "COMPLETE":
        raise ValueError("RPEval scoring has not settled")
    data = run.read(run.OUT / "SETTLED.json")
    ledger = {(r["unit"]["stage"], r["request_sha256"]): r for r in data["ledger"]}
    if len(ledger) != len(data["ledger"]) or len(ledger) != state["physical_requests"]:
        raise ValueError("RPEval terminal request count or deduplication disagrees")
    run.probe.OUT, run.probe.RUN = run.OUT, run.RUN
    actual = {}
    for stage in (run.ACTOR, run.JUDGE):
        for record, reply in run.probe.stage_receipts(stage).values():
            if (record is None or record["status"] == "PENDING_DELIVERY_UNKNOWN"
                    or (record["status"] == "OK") != bool(reply)):
                raise ValueError("A physical receipt is absent or not terminal")
            actual[stage, record["request_sha256"]] = record
    if actual != ledger:
        raise ValueError("Terminal ledger is not backed by its physical receipts")
    rows = data["rows"]
    if len(rows) != plan["assigned"] or set(data["answers"]) != set(plan["intervention_roots"]):
        raise ValueError("Treatment answers do not match the planned roster")
    report = run.parent.joint.parent.comparisons.grade_pair
    panels = run.subsets(rows, plan)
    panels["intervention"] = [row for row in rows if row["uid"] in data["answers"]]
    return {
        "strict_whole_answer_pairs": {name: {
            control: report(panel, control, run.ARM, "full_match")
            for control in (run.ablation.MAIN_ONLY, run.parent.GATE, run.parent.RP)
        } for name, panel in panels.items()},
        "receipt_hashes_verified": len(actual),
        "scores_modified": 0,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("allocation", "terminal"))
    phase = parser.parse_args().phase
    plan, audit = exposure()
    if phase == "terminal":
        audit.update(complete(plan))
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
