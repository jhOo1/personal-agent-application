"""Rebuild settled V42 requests and check which memory the Actor actually received."""
from collections import Counter, defaultdict
import json

from qamc.common import sha

import run_visibility_v42 as runner


def replay_stage(wave, stage, jobs, cache, counts):
    condition = cache[stage]
    needed, aliases = {}, []
    for uid, method, wire in jobs:
        key = sha(wire)
        if key in condition or key in needed:
            aliases.append({"uid": uid, "arm": method, "sha256": key})
        else:
            needed[key] = (uid, method, wire)
    actual = runner.read(runner.PROBE.OUT / (stage + "_MANIFEST.json"))
    if actual != runner.manifest(wave, stage, needed.values()):
        raise ValueError(f"{wave} {stage} actual requests differ from saved outcomes")
    if aliases != runner.read(runner.PROBE.OUT / (stage + "_REUSE.json")):
        raise ValueError(f"{wave} {stage} alias changed")
    observed = runner.PROBE.stage_receipts(stage)
    new = {key: list(observed[uid, method]) for key, (uid, method, _) in needed.items()}
    if new != runner.read(runner.PROBE.OUT / (stage + "_EXACT.json")):
        raise ValueError(f"{wave} {stage} actual receipts changed")
    condition.update(new)
    counts[stage + "/new"] += len(new)
    counts[stage + "/reuse"] += len(aliases)
    return new


def analyze():
    plan = runner.read(runner.OUT / "FROZEN.json")
    if plan != runner.prepare():
        raise ValueError("V42 code or parent artifacts differ from the freeze")
    archive = runner.read(runner.prior.OUT / "FROZEN.json")
    cache = runner.old_receipts(archive)
    roots = {root["uid"]: root for root in archive["roots"]}
    original = runner.read(runner.prior.formal.OUT / "PLAN.json")
    references = runner.prior.author_cases(original)
    totals, visibility = Counter(), Counter()
    compared = []
    selection_partitions = defaultdict(list)
    visibility_partitions = defaultdict(list)
    source_partitions = defaultdict(list)
    for index, uids in enumerate(plan["waves"]):
        wave = f"wave_{index:02d}"
        folder = runner.OUT / wave
        path = folder / "COMPLETED.json"
        if not path.exists():
            break
        saved = runner.read(path)
        if [row["uid"] for row in saved["rows"]] != uids:
            raise ValueError("Completed wave membership changed")
        runner.PROBE.OUT, runner.PROBE.RUN = folder, runner.RUN / wave
        selectors, actors, grades = [], [], []
        for row in saved["rows"]:
            uid = row["uid"]
            root = roots[uid]
            reference = references[uid]
            family = "development_transfer" if reference["legacy_same_configuration_uid"] else reference["track"]
            source_partitions[family].append(row)
            for method, chosen in row["selected"].items():
                wire = runner.selection_request(root, method)
                if sha(wire) != chosen["request_sha256"]:
                    raise ValueError("Unreproducible selection request")
                selectors.append((uid, method, wire))
                if chosen["scope"] is not None and runner.compile_scope(root, chosen["raw"]) != chosen["scope"]:
                    raise ValueError("Compiled scope differs from the saved selection")
            wires = {}
            for arm, (method, masked) in runner.ARMS.items():
                scope = row["selected"][method]["scope"]
                answer = row["answers"][arm]
                if scope is None:
                    if answer["status"] != "NO_VALID_SELECTOR":
                        raise ValueError("Actor executed with invalid selection")
                    continue
                wire = runner.actor_request(root, scope, masked=masked)
                view = json.loads(wire["messages"][1]["content"])
                if (sha(wire) != answer["request_sha256"]
                        or [src["memory_id"] for src in view["source_evidence"]] != answer["visible_ids"]):
                    raise ValueError("Actor exposure does not match recorded wire")
                wires[arm] = wire
                actors.append((uid, arm, wire))
                if answer["answer"] and not row["native"][arm].get("reuse"):
                    result = {"uid": uid, "method": runner.prior.GATE, "actor_status": "OK", "answer": answer["answer"]}
                    item, = runner.prior.formal.grading_jobs(original, [references[uid]], [result])
                    if sha(item["request"]) != row["native"][arm]["judge_sha256"]:
                        raise ValueError("Judge did not score the actual answer")
                    grades.append((uid, arm, item["request"]))
            labels = dict(zip((src["memory_id"] for src in root["original_sources"]),
                              row["labels"], strict=True))
            if {"SCOPED_FULL", "SCOPED_MASKED"} <= wires.keys():
                full, mask = wires["SCOPED_FULL"], wires["SCOPED_MASKED"]
                if full["messages"][0] != mask["messages"][0]:
                    raise ValueError("Visibility pair lost identical system prompts")
                left, right = (json.loads(wire["messages"][1]["content"]) for wire in (full, mask))
                if any(left.get(key) != right.get(key) for key in (
                    "query", "current_context", "facts", "memory_decision_scopes"
                )):
                    raise ValueError("Visibility pair changed task or scope")
                keep = {s["memory_id"] for s in right["source_evidence"]}
                if [s for s in left["source_evidence"] if s["memory_id"] in keep] != right["source_evidence"]:
                    raise ValueError("Retained evidence was rewritten")
                visibility["comparable_pairs"] += 1
                visibility["different_actor_wire"] += full != mask
                visibility["excluded_sources"] += len(left["source_evidence"]) - len(keep)
                hidden = [labels[src["memory_id"]] for src in left["source_evidence"]
                          if src["memory_id"] not in keep]
                partition = ("unchanged" if full == mask else "includes_author_BC" if set(hidden) - {"A"}
                             else "only_author_A")
                visibility_partitions[partition].append(row)
                visibility["removed_author_A"] += hidden.count("A")
                visibility["removed_author_B"] += hidden.count("B")
                visibility["removed_author_C"] += hidden.count("C")
                if full != mask:
                    compared.append(row)
            if {"DIRECT_MASKED", "SCOPED_MASKED"} <= wires.keys():
                levels = {}
                for method, value in row["selected"].items():
                    strength = dict.fromkeys(labels, "A")
                    for use in value["scope"]:
                        mid = use["memory_id"]
                        strength[mid] = max(strength[mid], use["level"])
                    levels[method] = strength
                direct, scoped = levels["DIRECT"], levels["SCOPED"]
                changes_bc = [(direct[mid], scoped[mid]) for mid, label in labels.items()
                              if label in "BC" and scoped[mid] != direct[mid]]
                fewer_a = sum(scoped[mid] != "A" for mid, label in labels.items() if label == "A") < sum(
                    direct[mid] != "A" for mid, label in labels.items() if label == "A")
                if any(right < left for left, right in changes_bc):
                    part = "lower_author_BC_strength"
                elif changes_bc:
                    part = "higher_author_BC_strength"
                else:
                    part = "fewer_author_A_preserves_BC_strength" if fewer_a else "other"
                selection_partitions[part].append(row)
        records = []
        for stage, jobs in ((runner.SELECTOR, selectors), (runner.ACTOR, actors), (runner.JUDGE, grades)):
            records.extend(record for record, _ in replay_stage(wave, stage, jobs, cache, totals).values())
        if records != saved["ledger"]:
            raise ValueError("Completed ledger differs from actual receipt files")
        totals["roots"] += len(saved["rows"])
    return {"checked": totals, "visibility": visibility,
            "activated_pair_native": runner.paired(compared, "SCOPED_FULL", "SCOPED_MASKED"),
            "visibility_partitions_by_author_labels": {
                key: runner.paired(rows, "SCOPED_FULL", "SCOPED_MASKED")
                for key, rows in visibility_partitions.items()
            },
            "selector_partitions_by_author_labels": {
                key: runner.paired(rows, "DIRECT_MASKED", "SCOPED_MASKED")
                for key, rows in selection_partitions.items()
            },
            "source_track_pairs": {track: {
                f"{left}__{right}": runner.paired(rows, left, right) for left, right in runner.COMPARISONS
            } for track, rows in source_partitions.items()},
            "source_track_label_pairs": {track: {
                label: {f"{left}__{right}": runner.paired(selected, left, right) for left, right in runner.COMPARISONS}
                for label, selected in (
                    ("all_A", [row for row in rows if set(row["labels"]) == {"A"}]),
                    ("contains_BC", [row for row in rows if set(row["labels"]) != {"A"}])
                )
            } for track, rows in source_partitions.items()},
            "new_model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
