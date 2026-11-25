"""Build matched revision requests from a fixed historical Actor request."""
from copy import deepcopy
import json

from frozen_decision import answer_digest, compile_option


COMMON = (
    "Revise the supplied answer only where the current task and historical evidence justify it. "
    "Protect explicit task requirements, true facts, and applicable restrictions. "
    "A personal preference alone cannot change a default for other participants. "
    "Use the language of the original task. Return only a JSON object. "
    'Return {"action":"keep"} if the current answer is better.'
)
INSTRUCTIONS = {
    "ordinary": 'Otherwise return {"action":"revise","answer":"the complete revised answer"}.',
    "option": (
        'Otherwise return {"action":"append","base_digest":"the provided digest",'
        '"choice_id":"personal_option","value":"one independently executable personal option"}. '
        "Do not append a choice that changes or contradicts the existing plan, needs another "
        "participant's agreement, or introduces an unsupported fact. Supply only the option value."
    ),
}


def option_request(original, answer, method):
    request = deepcopy(original)
    request["messages"].append({
        "role": "user",
        "content": COMMON + "\n" + INSTRUCTIONS[method] + "\n" + json.dumps(
            {"draft": answer, "base_digest": answer_digest(answer)}, ensure_ascii=False),
    })
    return request


def resolve_option(answer, serialized, method):
    proposal = json.loads(serialized)
    if proposal == {"action": "keep"}:
        return answer
    if method == "option":
        label = "个人可选项" if any("\u4e00" <= ch <= "\u9fff" for ch in answer) else "Personal option"
        return compile_option(answer, proposal, {"personal_option": label})
    if not isinstance(proposal, dict) or set(proposal) != {"action", "answer"}:
        raise ValueError("Invalid revision")
    revised = proposal["answer"]
    if proposal["action"] != "revise" or not isinstance(revised, str) or not revised.strip():
        raise ValueError("Invalid revision content")
    return revised
