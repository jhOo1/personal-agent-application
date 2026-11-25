"""Render an independent personal choice without editing a shared answer."""
from hashlib import sha256


def answer_digest(answer):
    return sha256(answer.encode("utf-8")).hexdigest()


def compile_option(shared_answer, proposal, eligible_choices):
    """Apply at most one personal option using an upstream selection of slots.

    Slot eligibility describes model-predicted independence. The compiler
    enforces byte preservation of the given default, not semantic agreement.
    """
    if not isinstance(proposal, dict):
        raise ValueError("Expected a proposal object")
    if proposal == {"action": "keep"}:
        return shared_answer
    fields = {"action", "base_digest", "choice_id", "value"}
    if set(proposal) != fields or proposal["action"] != "append":
        raise ValueError("Invalid personal option contract")
    if proposal["base_digest"] != answer_digest(shared_answer):
        raise ValueError("Option belongs to another shared answer")
    choice, value = proposal["choice_id"], proposal["value"]
    if not isinstance(choice, str) or choice not in eligible_choices:
        raise ValueError("Unknown independent choice")
    if not isinstance(value, str) or not value.strip() or len(value) > 240:
        raise ValueError("Invalid option value")
    if any(character in value for character in "\r\n"):
        raise ValueError("Expected a single inline option")
    label = eligible_choices[choice]
    return f"{shared_answer}\n\n{label}：{value.strip()}"
