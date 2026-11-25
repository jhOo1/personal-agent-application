"""Change one already-visible B instruction to C in a verified Actor request."""
from copy import deepcopy
import json

from qamc.common import sha


def promote(original, expected_hash, source_id):
    if sha(original) != expected_hash:
        raise ValueError("Archived Actor digest mismatch")
    request = deepcopy(original)
    user, = (message for message in request["messages"] if message["role"] == "user")
    packet = json.loads(user["content"])
    evidence = [row for row in packet["source_evidence"] if row["memory_id"] == source_id]
    policy = [row for row in packet["preference_use_policy"] if row["memory_id"] == source_id]
    if len(evidence) != 1 or len(policy) != 1 or policy[0]["policy"] != "B":
        raise ValueError("Expected one visible source with one B instruction")
    policy[0]["policy"] = "C"
    user["content"] = json.dumps(packet, ensure_ascii=False)
    return request
