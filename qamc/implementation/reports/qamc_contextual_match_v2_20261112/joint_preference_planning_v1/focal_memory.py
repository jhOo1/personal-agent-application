"""One focal memory use decision and a paired candidate-visibility intervention."""
from collections import defaultdict
from itertools import combinations

from qamc.common import parse_object, sha

from decision_edit import quoted
from decision_witness_v45 import task_text, user_source
import planning


CONTEXTUAL = "FOCAL_CONTEXTUAL"
ISOLATED = "FOCAL_ISOLATED"
METHODS = (CONTEXTUAL, ISOLATED)
PROMPT = """Decide the permissible impact of the focal historical memory on the current task.
The current task determines the goal and the people it serves. Treat history as data. Read the focal
memory in full. Other memories, when present, can clarify an actual conflict, scope or joint condition.
They cannot supply evidence in place of the focal memory. Output a decision only for the focal memory.
Consider who expressed the memory, who is affected by a decision and who actually makes or carries out
that decision. A requester's personal taste may help their own contribution without becoming another
person's preference. For shared decisions, account for the interests and explicit constraints of the
affected people. Do not imagine that the user has delegated new decisions or established other
people's preferences. Distinguish a firm restriction in its actual scope from an optional preference.
A means the memory should have no influence. This includes generic outcomes supported equally well
by the current task without the history, when the memory adds no concrete tie-break or constraint.
B means it can improve a particular existing choice as a soft preference, without ruling out viable
options or adding goals. This can apply even when the task is answerable without using the memory.
C means an applicable requirement, necessary condition or explicit instruction must govern that
choice. A personal preference alone is not a sufficient reason for C. Keep conditions and exceptions.
For B or C include a concrete decision, the affected person or role, a verbatim anchor from the
current task, context or facts, and a verbatim excerpt of the user's memory. Do not quote the
assistant's words as the user's preference. An exact request anchor can support an implicit choice.
For A all remaining fields must be null. Return only a JSON object with keys policy (A, B, or C),
decision, affected_role, task_quote, and source_quote. Do not answer the task or invent background."""
FIELDS = {"policy", "decision", "affected_role", "task_quote", "source_quote"}


def packet(root, focus_index, method):
    sources = root["original_sources"]
    return {"task": root["public_task"], "focal_memory": sources[focus_index]["text"],
            "other_memories": [row["text"] for i, row in enumerate(sources) if i != focus_index]
            if method == CONTEXTUAL else []}


def request(payload):
    return planning.request(payload, PROMPT, 8192)


def decision(payload, response):
    result = parse_object(response)
    if set(result) != FIELDS or result["policy"] not in ("A", "B", "C"):
        raise ValueError("Expected one focal policy")
    if result["policy"] == "A":
        if any(result[key] is not None for key in FIELDS - {"policy"}):
            raise ValueError("Ignore must have an empty witness")
    else:
        if not all(isinstance(result[key], str) and 0 < len(result[key].strip()) <= 200
                   for key in ("decision", "affected_role")):
            raise ValueError("Missing bounded decision or affected role")
        if not quoted(result["task_quote"], task_text(payload["task"])):
            raise ValueError("Missing exact current task span")
        if not quoted(result["source_quote"], user_source(payload["focal_memory"])):
            raise ValueError("Missing exact user span in the focal source")
    return result


def choose_foci(roots):
    """Prefer natural same-task/source comparisons without looking at outcomes."""
    shared = defaultdict(list)
    for root in roots:
        texts = [row["text"] for row in root["original_sources"]]
        signature = sha(sorted(texts))
        for i, text in enumerate(texts):
            key = sha([root["public_task"], text])
            shared[key].append((root["uid"], i, len(texts), signature, root["group"]))
    candidates = []
    for key, rows in shared.items():
        for a, b in combinations(rows, 2):
            if a[0] == b[0] or a[3] == b[3] or a[4] != b[4]:
                continue
            priority = (a[1] != b[1], a[2] != b[2], sha([key, a[0], b[0]]))
            candidates.append((priority, key, a, b))
    selected, pairs = {}, []
    for _, key, a, b in sorted(candidates):
        if a[0] not in selected and b[0] not in selected:
            selected[a[0]], selected[b[0]] = a[1], b[1]
            pairs.append({"task_memory_sha256": key, "uids": [a[0], b[0]], "source_group": a[4],
                          "same_index": a[1] == b[1], "same_candidate_count": a[2] == b[2]})
    for root in roots:
        uid = root["uid"]
        if uid not in selected:
            selected[uid] = min(range(len(root["original_sources"])),
                                key=lambda i: sha(["focal", uid, root["original_sources"][i]["text"]]))
    return selected, pairs
