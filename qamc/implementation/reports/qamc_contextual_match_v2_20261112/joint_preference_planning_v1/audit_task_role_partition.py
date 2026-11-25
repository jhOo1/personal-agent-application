"""Compare task-only role outputs with the existing development eligibility audit."""
from collections import Counter
import json

from qamc.common import sha

import run_task_decision_roles as run


def separate_slots(roles):
    decisions = [role for role in roles if role["kind"] == "DECISION"]
    requester = [role["slot"] for role in decisions if role["beneficiary"] == "SELF"]
    external = [role["slot"] for role in decisions if role["beneficiary"] in ("OTHER", "SHARED")]
    execution = [role["slot"] for role in decisions if role["executor"] == "SELF"]
    return {"requester_benefits": requester, "external_benefits": external, "requester_executes": execution}


def audit():
    out = run.OUT
    settled_path = out / "SETTLED.json"
    eligibility_path = out / "PARTITION_ELIGIBILITY.json"
    settled, eligibility = run.read(settled_path), run.read(eligibility_path)
    freeze = run.read(out / "FROZEN.json")
    contracts = settled["contracts"]
    requests = {key: row["request_sha256"] for key, row in contracts.items()}
    if requests != freeze["wire_shas"]:
        raise ValueError("Task role receipts disagree with the frozen request set")
    tasks = {row["task_sha256"]: row for row in settled["rows"]}
    if tasks.keys() != contracts.keys():
        raise ValueError("Task role receipts do not cover the declared tasks")
    panels = {}
    for name, panel in eligibility["panels"].items():
        overlap = []
        for task in panel["tasks"]:
            key = task["task_sha256"]
            if key not in contracts:
                continue
            archived = tasks[key]
            if sha(archived["task"]) != key or archived["task"]["query"] != task["query"]:
                raise ValueError("Eligibility audit and role diagnostic disagree on current task")
            result = contracts[key]
            partition = separate_slots(result["roles"])
            if result["status"] != "OK":
                disposition = "UNAVAILABLE"
            elif partition["requester_benefits"] and partition["external_benefits"]:
                disposition = "HAS_BOTH_BENEFICIARY_TYPES"
            else:
                disposition = "NO_SEPARATE_BENEFICIARY_TYPES"
            choices = [{"choice": choice, "role": role}
                       for choice, role in zip(archived["choices"], result["roles"], strict=True)] if result["roles"] else []
            overlap.append({**task, "automatic": disposition, "slots": partition, "choices": choices,
                            "request_sha256": result["request_sha256"], "response_status": result["status"]})
        cells = []
        counts = Counter((row["classification"], row["automatic"]) for row in overlap)
        for (classification, automatic), count in sorted(counts.items()):
            members = [row for row in overlap
                       if (row["classification"], row["automatic"]) == (classification, automatic)]
            cells.append({"eligibility": classification, "automatic": automatic, "tasks": count,
                          "histories": len({uid for row in members for uid in row["members"]}),
                          "source_groups": len({group for row in members for group in row["source_groups"]})})
        panels[name] = {"tasks_with_role_requests": len(overlap), "cells": cells, "tasks": overlap}
    return {"settled_sha256": sha(settled_path.read_bytes()), "eligibility_sha256": sha(eligibility_path.read_bytes()),
            "additional_model_requests": 0, "eligibility_is_development_review": True, "panels": panels}


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
