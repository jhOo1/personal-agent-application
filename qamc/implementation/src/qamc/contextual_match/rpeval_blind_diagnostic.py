"""Secondary observed-use diagnostic; author labels are never in Judge input.

This is not the benchmark's native score. It does not overwrite native grades.
"""
from qamc.common import parse_object
from .development import text_request

PROMPT = """Assess how the answer actually uses each supplied memory, independently
of what the desired use should be. You do not receive author intent labels.
Output only {"observed_policy":"ABC...","evidence":["exact answer substring or empty",...]}.
Use original memory order. Exactly one letter and one evidence item per memory.
A: the memory does not materially influence this answer. Shared topic words or
generic suggestions alone do not prove personal-memory use; evidence must be empty.
B: the memory meaningfully tailors a choice or expression, while ordinary task
goals remain in control. Cite a short exact answer substring showing that use.
C: the memory drives the answer's principal choice, priority or binding constraint.
An enforced hard negative/dietary/ethical requirement can be C without dominating
the word count. Cite a short exact answer substring demonstrating this influence.
Do not judge whether A/B/C is desirable; do not infer a hidden desired label from
the query. Do not reward agreement with any preference. Track actual use and
preserve attribution/conditions. Quotes must be verbatim, not paraphrases.
"""


def request(task, answer):
    return text_request(PROMPT, {"query":task.query,
        "memories":[m.text for m in task.memories], "answer":answer}, cap=4096)


def parse(task, answer, raw):
    obj = parse_object(raw)
    if not isinstance(obj, dict) or set(obj) != {"observed_policy", "evidence"}:
        raise ValueError("Invalid observed-use diagnostic envelope")
    policy, evidence = obj["observed_policy"], obj["evidence"]
    if not isinstance(policy, str) or len(policy) != len(task.memories) or set(policy)-set("ABC"):
        raise ValueError("Invalid observed-use policy")
    if not isinstance(evidence, list) or len(evidence) != len(policy):
        raise ValueError("Diagnostic evidence alignment changed")
    for label, quote in zip(policy, evidence, strict=True):
        if not isinstance(quote, str) or (label == "A" and quote != ""):
            raise ValueError("Invalid A evidence")
        if label != "A" and (not quote.strip() or quote not in answer):
            raise ValueError("Diagnostic evidence not in actual answer")
    return obj


def author_policy(reference):
    """Evaluation-only aliases already used by the native rubric adapter."""
    value = reference["intent_type"]
    if isinstance(reference["persona"], list):
        if not isinstance(value, str) or len(value) != len(reference["persona"]) or set(value)-set("ABC"):
            raise ValueError("Unknown multi author policy")
        return value
    aliases = {"ignore":"A", "irrelevant":"A", "忽略偏好":"A",
               "support":"B", "supportive":"B", "支持性偏好":"B",
               "dominate":"C", "dominant":"C", "以偏好为主线":"C"}
    if value not in aliases:
        raise ValueError("Unknown single author policy")
    return aliases[value]
