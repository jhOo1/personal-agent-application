"""Read-only audit of archived-RP edit locality, source citations and exact reuse."""
from collections import Counter, defaultdict
import json
from statistics import median

from qamc.common import sha

from decision_edit import quoted, task_text
import run_seed_control as seed


def replay_task_only_role_metadata(packet, raw, result):
    """Measure one contract ambiguity without substituting a candidate or score."""
    if result["status"] != "INVALID_REFERENCE":
        return None
    rejected = result["rejected"]
    if any(row["reason"] != "role_without_memory" for row in rejected):
        return None
    task = tuple(task_text(packet["task"]))
    proposal = json.loads(raw)
    for row in rejected:
        operation = proposal["replace_ops"][row["index"]]
        if not quoted(operation["role_quote"], task):
            return "INVALID_TASK_ROLE_QUOTE"
        operation["role_quote"] = None
    return seed.edit.compile_revision(packet, json.dumps(proposal))["status"]


def audit():
    frozen, state = (seed.read(seed.OUT / name) for name in ("FROZEN.json", "RUN_STATE.json"))
    manifest = seed.read(seed.OUT / f"{seed.PLAN}_MANIFEST.json")
    jobs = {sha(job["request"]): job for job in manifest["units"]}
    if jobs.keys() != set(frozen["wire_sha256"].values()) or len(jobs) != len(manifest["units"]):
        raise ValueError("Revision manifest differs from the frozen tasks")
    reference = seed.read(seed.joint.parent.OUT / "SETTLED.json")
    original = {row["uid"]: row for row in reference["rows"]}
    if original.keys() != frozen["wire_sha256"].keys():
        raise ValueError("Revision tasks and stored native scores differ")

    seed.probe.OUT, seed.probe.RUN = seed.OUT, seed.RUN
    physical = seed.probe.stage_receipts(seed.PLAN)
    counts, citations, failures, by_status, details = (
        Counter(), Counter(), Counter(), defaultdict(Counter), {},
    )
    deltas, role_metadata_replays = [], {}
    for uid, digest in frozen["wire_sha256"].items():
        job = jobs[digest]
        unit = job["unit"]
        receipt, raw = physical[unit["root_id"], unit["method"]]
        if receipt is None or receipt["status"] != "OK":
            status = receipt["status"] if receipt is not None else "UNISSUED"
            details[uid] = {"status": status, "request_sha256": digest}
            counts[status] += 1
            continue
        if receipt["request_sha256"] != digest or sha(job["request"]) != digest:
            raise ValueError("Revision reply differs from the public request")
        packet = json.loads(job["request"]["messages"][1]["content"])
        labels = original[uid]["labels"]
        memory_ids = [row["memory_id"] for row in packet["source_evidence"]]
        if len(memory_ids) != len(set(memory_ids)) or len(memory_ids) != len(labels):
            raise ValueError("Memory citations cannot be aligned with author labels")
        author = dict(zip(memory_ids, labels, strict=True))
        profile = "all_A" if set(labels) == {"A"} else ("contains_C" if "C" in labels else "B_without_C")
        try:
            result = seed.edit.compile_revision(packet, raw)
        except (TypeError, ValueError) as exc:
            result = {"status": "INVALID_REVISION_CONTRACT", "error": str(exc)}
        status = result["status"]
        counts[status] += 1
        by_status[profile][status] += 1
        details[uid] = {k: v for k, v in result.items() if k != "answer"}
        details[uid]["request_sha256"] = digest
        if status == "INVALID_REFERENCE":
            failures.update(rejected["reason"] for rejected in result["rejected"])
            replay_status = replay_task_only_role_metadata(packet, raw, result)
            if replay_status is not None:
                role_metadata_replays[uid] = replay_status
        if status in ("APPLIED", "NOOP"):
            before = packet["original_answer"]
            if status == "NOOP" and result["answer"] != before:
                raise ValueError("An empty edit list changed the stored RP answer")
            if status == "APPLIED":
                deltas.append(result["characters"])
                for operation in json.loads(raw)["replace_ops"]:
                    memory = operation["memory"]
                    citations[author[memory["id"]] if memory else "TASK_ONLY"] += 1
                    if operation["role_quote"] is not None:
                        citations["WITH_ROLE_QUOTE"] += 1

    if state["state"] == "COMPLETE":
        rows = seed.read(seed.OUT / "SETTLED.json")["rows"]
        if (len(rows) != len(details)
                or any(details[row["uid"]]["status"] != row["revision"]["status"]
                       or details[row["uid"]].get("answer_sha256") != row["revision"].get("answer_sha256")
                       for row in rows)):
            raise ValueError("Audit and settled revisions differ")
    return {
        "assigned": len(details), "state_at_read": state["state"],
        "physical_status": Counter(receipt["status"] for receipt, _ in physical.values() if receipt),
        "logical_revision_status": counts, "archived_author_profile_on_replied_tasks": by_status,
        "citations_in_applied_operations": citations, "invalid_reference_reasons": failures,
        "task_only_role_metadata_replay": {
            "statuses": Counter(role_metadata_replays.values()),
            "per_case": role_metadata_replays,
            "interpretation": "Only valid task role quotes on otherwise task-only edits are removed. "
                              "The original frozen status, answer and score are never modified.",
        },
        "median_changed_characters": {field: median(row[field] for row in deltas) if deltas else None
                                     for field in ("removed", "inserted")},
        "interpretation": "Citation labels describe the source, not the action taken. An A citation can support "
                          "removing a misuse. These audit counts do not establish semantic correctness.",
        "per_case": details,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
