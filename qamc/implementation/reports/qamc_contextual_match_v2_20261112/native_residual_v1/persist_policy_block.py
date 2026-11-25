"""Bound mutations to the archived PersistBench memory-use policy."""
from copy import deepcopy

from qamc.common import sha

START = "## Memory Usage Guidelines\n"
END = "\nWhen uncertain, follow these priorities:"


def locate(system):
    if system.count(START) != 1:
        raise ValueError("Expected one memory guideline header")
    start = system.index(START) + len(START)
    end = system.find(END, start)
    if end < start or "<memories>" in system[start:end]:
        raise ValueError("Expected the guideline footer before evidence")
    return system[:start], system[start:end], system[end:]


def policy_wire(original, original_sha, mutation, mode, *, byte_cap):
    if sha(original) != original_sha:
        raise ValueError("Archived Actor request digest mismatch")
    if not isinstance(mutation, str) or not mutation.strip():
        raise ValueError("Expected nonempty policy mutation")
    if any(marker in mutation for marker in (START.strip(), END.strip(), "<memories>", "</memories>")):
        raise ValueError("Mutation cannot insert prompt boundary markers")
    request = deepcopy(original)
    systems = [m for m in request["messages"] if m["role"] == "system"]
    if len(systems) != 1 or not isinstance(systems[0]["content"], str):
        raise ValueError("Expected one textual system message")
    prefix, original_block, suffix = locate(systems[0]["content"])
    if mode == "append":
        block = original_block.rstrip() + "\n\n" + mutation.strip() + "\n"
    elif mode == "replace":
        block = "\n" + mutation.strip() + "\n"
    else:
        raise ValueError("Unknown mutation mode")
    if len(block.encode()) > byte_cap or block.strip() == original_block.strip():
        raise ValueError("Policy exceeds budget or makes no change")
    systems[0]["content"] = prefix + block + suffix
    return request
