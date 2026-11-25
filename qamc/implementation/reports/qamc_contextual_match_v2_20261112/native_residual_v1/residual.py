"""Pure generation-wire transform and equally bounded policy proposals."""
from copy import deepcopy

from qamc.common import sha

MAX_RULES = 3
MAX_POLICY_BYTES = 1024


def policy(rules):
    if not isinstance(rules, (list, tuple)) or len(rules) > MAX_RULES:
        raise ValueError("Expected at most three rules")
    if any(not isinstance(rule, str) or not rule.strip() or rule != rule.strip()
           or "\n" in rule or "\r" in rule for rule in rules):
        raise ValueError("Expected a single nonempty line per rule")
    if len(set(rules)) != len(rules) or len("\n".join(rules).encode()) > MAX_POLICY_BYTES:
        raise ValueError("Duplicate rules or policy exceeds byte limit")
    return tuple(rules)


def atomic(parent, operation, index, rule=None):
    rules = list(policy(parent))
    if type(index) is not int:
        raise ValueError("Invalid mutation index")
    if operation == "ADD" and 0 <= index <= len(rules):
        rules.insert(index, rule)
    elif operation == "REPLACE" and 0 <= index < len(rules):
        rules[index] = rule
    elif operation == "DELETE" and 0 <= index < len(rules) and rule is None:
        del rules[index]
    else:
        raise ValueError("Invalid mutation")
    result = policy(rules)
    if result == tuple(parent):
        raise ValueError("Mutation leaves policy unchanged")
    return result


def actor_wire(original, original_sha, rules, *, history_enabled):
    if sha(original) != original_sha:
        raise ValueError("Archived Actor request digest mismatch")
    rules = policy(rules)
    if type(history_enabled) is not bool:
        raise ValueError("Unknown history exposure")
    if not rules or not history_enabled:
        return original
    request = deepcopy(original)
    systems = [message for message in request["messages"] if message["role"] == "system"]
    if len(systems) != 1 or not isinstance(systems[0]["content"], str):
        raise ValueError("Expected one text system message")
    systems[0]["content"] += "\n\nAdditional response guidance:\n" + "\n".join(
        f"- {rule}" for rule in rules
    )
    return request
