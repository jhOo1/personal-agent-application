"""Compile an extractive change to one source in a frozen Actor request."""
from copy import deepcopy
import json

from qamc.common import sha


def project(original, expected_sha, source_id, spans):
    if sha(original) != expected_sha:
        raise ValueError("Archived Actor request digest mismatch")
    request = deepcopy(original)
    user, = (message for message in request["messages"] if message["role"] == "user")
    packet = json.loads(user["content"])
    source, = (row for row in packet["source_evidence"] if row["memory_id"] == source_id)
    text = source["text"]
    if not spans:
        return original
    pieces, previous_end = [], 0
    for start, end in spans:
        if type(start) is not int or type(end) is not int:
            raise ValueError("Expected integer offsets")
        if not previous_end <= start < end <= len(text):
            raise ValueError("Spans must be ordered, disjoint and in bounds")
        pieces.append(text[start:end])
        previous_end = end
    # Keep excerpts visually separate. The caller must verify each retained
    # passage and its dependencies before claiming semantic preservation.
    projected = "\n[…]\n".join(pieces)
    if len(projected) >= len(text) or not projected.strip():
        raise ValueError("Expected a nonempty shorter source")
    source["text"] = projected
    user["content"] = json.dumps(packet, ensure_ascii=False)
    return request
