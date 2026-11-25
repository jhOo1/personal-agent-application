"""Offline acceptance of fixed-answer comparison requests on the exposed RPEval panel."""
from collections import Counter
import json
from pathlib import Path

from proposals.qamc_protocol_alignment.sampling import validate_public_request
from qamc.common import sha

import run_policy_override_v43 as study
from score_task_only import saved_drafts

COMMON = """Select the stronger existing answer to the current request. Both answers are complete candidates.
Read the current task first. Preserve every applicable hard constraint and valuable soft preference.
Treat the archived preference-use policy as fallible evidence. The historical user may not be the beneficiary,
and suggestions a previous assistant made are not the user's preferences. Keep independently useful task content.
Use only the supplied task, sources and candidates. Return exactly {"choice":"X"} or {"choice":"Y"} as JSON."""

METHOD_PROMPTS = {
    "GENERIC": """Use careful comparative review. Check instruction adherence, factual consistency, completeness,
appropriateness and the strength of any personalization. Select the better usable answer overall.""",
    "DECISION_EVIDENCE": """Compare differences in the actual decisions, options, constraints and attribution in the two answers.
For a differing decision, check which person or group it affects and whether the current request establishes that decision.
Use the task-only draft as a witness of what the request itself can support. A similarity to memory alone does not establish
dependence on memory. The task-only draft can miss or misrepresent requirements, so independently check the current task.
Prefer the task-only draft only when it removes an unsupported use of history or a material task error and preserves applicable
soft preferences, hard constraints and task completeness. If it loses valid personalization, or the proposed improvement is
only a stylistic change or a disputed attribution, prefer the archived RP draft.""",
}


def packet(root, rp, baseline):
    if not isinstance(rp, str) or not isinstance(baseline, str) or not rp.strip() or not baseline.strip():
        raise ValueError("A selectable option must be an intact saved answer")
    choices = [
        {"id": "X", "generation_context": "RP", "answer": rp},
        {"id": "Y", "generation_context": "CURRENT_TASK_ONLY", "answer": baseline},
    ]
    if int(sha(["fixed-answer-comparison", root["uid"]])[:2], 16) % 2:
        choices.reverse()
        for identifier, option in zip(("X", "Y"), choices, strict=True):
            option["id"] = identifier
    return {
        "task": root["public_task"], "source_evidence": root["original_sources"],
        "archived_preference_use_policy": root["archived_policy"], "candidates": choices,
    }


def request(payload, method):
    wire = {"model": "qwen3.8-flash", "temperature": 0, "max_tokens": 8192, "stream": True,
            "stream_options": {"include_usage": True}, "messages": [
                {"role": "system", "content": COMMON + "\n\n" + METHOD_PROMPTS[method]},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]}
    validate_public_request(wire)
    return wire


def execute_choice(payload, raw):
    value = json.loads(raw, object_pairs_hook=lambda pairs: pairs)
    if value not in ([("choice", "X")], [("choice", "Y")]):
        raise ValueError("Invalid fixed-answer choice")
    chosen, = (item for item in payload["candidates"] if item["id"] == value[0][1])
    return chosen["answer"]


def preflight():
    v43, origins = study.prepare()
    if study.read(study.OUT / "FROZEN.json") != v43:
        raise ValueError("Frozen originals changed")
    plan = study.read(study.prior.OUT / "FROZEN.json")
    drafts = saved_drafts(plan)
    rows, missing, order, groups = [], {}, Counter(), set()
    for root in plan["roots"]:
        uid, wire = root["uid"], root["task_wire_sha256"]
        if origins[uid] != root or sha(study.prior.task_only_request(root)) != wire:
            raise ValueError("Historical task/evidence cannot be matched")
        record = drafts[wire]
        rp = root["archived"][study.prior.RP]["answer"]
        task_only = record["answer"]
        if not task_only:
            missing[uid] = record["record"]["status"] if record["record"] else "MISSING_DRAFT_RECEIPT"
        elif rp == task_only:
            rows.append({"uid": uid, "group": root["group"], "status": "IDENTICAL_ANSWER",
                         "answer_sha256": sha(rp)})
        else:
            payload = packet(root, rp, task_only)
            wires = {m: request(payload, m) for m in METHOD_PROMPTS}
            if len({w["messages"][1]["content"] for w in wires.values()}) != 1:
                raise ValueError("Methods must see the exact same task, evidence and options")
            for option in payload["candidates"]:
                if execute_choice(payload, json.dumps({"choice": option["id"]})) != option["answer"]:
                    raise ValueError("Chosen answer text changed")
            order[payload["candidates"][0]["generation_context"]] += 1
            groups.add(root["group"])
            rows.append({"uid": uid, "group": root["group"], "status": "BOTH_DRAFTS",
                         "task_wire_sha256": wire, "RP_actor_sha256": root["archived_actor_sha256"],
                         "choice_source": {o["id"]: o["generation_context"] for o in payload["candidates"]},
                         "answer_sha256": {o["id"]: sha(o["answer"]) for o in payload["candidates"]},
                         "request_sha256": {m: sha(w) for m, w in wires.items()}})
    return {
        "state": "OFFLINE_PREFLIGHT_ONLY",
        "new_model_calls": 0,
        "frozen_roots": len(plan["roots"]),
        "source_groups_with_both_distinct_drafts": len(groups),
        "answer_first": order,
        "planned_max_choice_requests": sum(order.values()) * len(METHOD_PROMPTS),
        "new_actor_or_judge_requests": 0,
        "missing": missing,
        "rows": rows,
        "code_sha256": sha(Path(__file__).read_bytes()),
    }


if __name__ == "__main__":
    print(json.dumps(preflight(), ensure_ascii=False, indent=2))
