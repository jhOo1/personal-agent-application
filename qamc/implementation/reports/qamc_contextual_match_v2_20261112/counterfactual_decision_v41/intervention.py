"""Build the paired draft intervention and matched final review requests."""

from copy import deepcopy
import json

from qamc.common import sha

FINAL_REVIEW = """
Use the original public task, original evidence and predicted preference-use policy to write
a concise, complete final answer. The two drafts are proposals. Retain valid applicable
preferences and explicit requirements even if either draft omitted them. Keep the original
task, speaker attribution and supplied facts. Neither draft is automatically preferred.
Return only JSON with keys "answer" (the user-facing answer) and "changes" (a list).
Each change has exactly "decision" (short description), "disposition" (KEEP, REJECT or RESTORE),
and "source_ids" (list of original memory IDs, empty when grounded only in the current task).
Record material changes only. The final answer must stand on its own, without this audit.
""".strip()

REVIEW_INSTRUCTIONS = {
    "DELTA": (
        "Draft A had the supplied history and draft B had only the current task. Compare actual "
        "options, rankings, constraints and affected parties. Treat each difference as a possible "
        "effect of history, then check its support in the source, predicted policy and current task. "
        "Keep justified effects, reject unsupported effects and restore applicable omitted preferences."
    ),
    "REVIEW": (
        "Review both drafts to make the best answer for the user. Check factual accuracy, relevance, "
        "task completion, ranking of recommendations, beneficiaries, constraints and use of history. "
        "Keep the useful parts, correct any unsupported claims or misapplied preferences and fill "
        "missing requirements. Use the original task and evidence to resolve disagreements."
    ),
}


def archived_packet(root):
    request = root["archived_actor_request"]
    if sha(request) != root["archived_actor_sha256"]:
        raise ValueError("Archived Actor wire hash mismatch")
    system, user = request["messages"]
    if [system["role"], user["role"]] != ["system", "user"]:
        raise ValueError("Unexpected archived Actor roles")
    packet = json.loads(user["content"])
    expected = {**root["public_task"], "source_evidence": root["original_sources"],
                "preference_use_policy": root["archived_policy"]}
    if packet != expected:
        raise ValueError("Public task or source policy changed")
    return request, packet


def render(request, packet, suffix):
    wire = deepcopy(request)
    wire["messages"][0]["content"] += "\n\n" + suffix
    wire["messages"][1]["content"] = json.dumps(packet, ensure_ascii=False)
    return wire


def task_only_request(root):
    request, packet = archived_packet(root)
    wire = deepcopy(request)
    wire["messages"][1]["content"] = json.dumps(
        {**packet, "source_evidence": [], "preference_use_policy": []}, ensure_ascii=False
    )
    return wire


def final_requests(root, *, archived_draft, task_only_draft):
    if not (isinstance(archived_draft, str) and archived_draft.strip()
            and isinstance(task_only_draft, str) and task_only_draft.strip()):
        raise ValueError("Both draft answers are required")
    request, packet = archived_packet(root)
    data = {**packet, "draft_a": archived_draft, "draft_b": task_only_draft}
    return {arm: render(request, data, FINAL_REVIEW + "\n\n" + instructions)
            for arm, instructions in REVIEW_INSTRUCTIONS.items()}


def parse_final(raw, root):
    obj = json.loads(raw)
    if (not isinstance(obj, dict) or set(obj) != {"answer", "changes"}
            or not isinstance(obj["answer"], str) or not obj["answer"].strip()
            or not isinstance(obj["changes"], list)):
        raise ValueError("Invalid final answer contract")
    ids = {row["memory_id"] for row in root["original_sources"]}
    for change in obj["changes"]:
        if (not isinstance(change, dict)
                or set(change) != {"decision", "disposition", "source_ids"}
                or not isinstance(change["decision"], str) or not change["decision"].strip()
                or change["disposition"] not in ("KEEP", "REJECT", "RESTORE")
                or not isinstance(change["source_ids"], list)
                or any(not isinstance(data, str) or data not in ids for data in change["source_ids"])
                or len(set(change["source_ids"])) != len(change["source_ids"])):
            raise ValueError("Invalid description or source attribution")
    return obj
