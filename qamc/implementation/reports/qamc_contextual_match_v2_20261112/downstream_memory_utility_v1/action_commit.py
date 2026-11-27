"""Copy-only action submission for shared, frozen complete Actor candidates.

The caller supplies lossless blocks from the existing answer segmenter. A
transaction transfers one action from one donor, potentially across several
ordered ranges. Semantic dependencies are identified by the controller.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Commit:
    answer: str
    outcome: str
    base: str
    donor: str | None = None
    replaced_blocks: int = 0
    copied_blocks: int = 0


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Transaction contains a duplicate key")
        result[key] = value
    return result


def _span(bounds, size, previous_stop, *, allow_insert=False):
    if not isinstance(bounds, list) or len(bounds) != 2 or any(type(i) is not int for i in bounds):
        raise ValueError("A block range must contain two integer boundaries")
    start, stop = bounds
    if not previous_stop <= start <= stop <= size or (start == stop and not allow_insert):
        raise ValueError("A block range is empty, overlapping, out of order, or outside the candidate")
    return start, stop


def submit(raw: str, candidates: Mapping[str, Sequence[str]], fallback: str,
           protected_literals: Sequence[str] = ()) -> Commit:
    """Apply a controller response, or retain the fixed fallback on contract error.

    Each replacement uses half-open block ranges. The strings of all unchanged
    blocks and all inserted donor blocks are preserved byte for byte. An
    inserted range can have an empty base range. The operation cannot remove
    a block without supplying a donor range.
    """
    if fallback not in candidates:
        raise ValueError("The predetermined fallback candidate is missing")
    for blocks in candidates.values():
        if (not blocks or isinstance(blocks, str)
                or any(not isinstance(s, str) or not s for s in blocks)
                or not any(s.strip() for s in blocks)):
            raise ValueError("Candidate blocks must reconstruct a nonempty answer")
    fallback_answer = "".join(candidates[fallback])
    if any(not literal or literal not in fallback_answer for literal in protected_literals):
        raise ValueError("Protected literal is missing from the fixed fallback")
    try:
        program = json.loads(raw, object_pairs_hook=_unique_keys)
        if not isinstance(program, dict):
            raise ValueError("Expected transaction object")
        mode = program.get("mode")
        base_id = program.get("base")
        if not isinstance(base_id, str) or base_id not in candidates:
            raise ValueError("Unknown base candidate")
        base = candidates[base_id]
        if mode == "SELECT" and program.keys() == {"mode", "base"}:
            answer = "".join(base)
            result = Commit(answer, "SELECTED", base_id)
        elif mode == "COMMIT" and program.keys() == {"mode", "base", "donor", "replacements"}:
            donor_id = program["donor"]
            if not isinstance(donor_id, str) or donor_id == base_id or donor_id not in candidates:
                raise ValueError("Unknown or identical donor")
            donor = candidates[donor_id]
            edits = program["replacements"]
            if not isinstance(edits, list) or not 1 <= len(edits) <= len(donor):
                raise ValueError("Expected a nonempty replacement inventory")
            parts = []
            base_stop = donor_stop = replaced = copied = 0
            previous_start = -1
            for edit in edits:
                if not isinstance(edit, dict) or edit.keys() != {"base", "donor"}:
                    raise ValueError("Expected only base and donor ranges")
                start, stop = _span(edit["base"], len(base), base_stop, allow_insert=True)
                first, last = _span(edit["donor"], len(donor), donor_stop)
                if start <= previous_start:
                    raise ValueError("Replacement locations must be distinct and increasing")
                parts.extend(base[base_stop:start])
                parts.extend(donor[first:last])
                base_stop, donor_stop, previous_start = stop, last, start
                replaced += stop - start
                copied += last - first
            parts.extend(base[base_stop:])
            if any(not block.endswith("\n") and not following.startswith("\n")
                   for block, following in zip(parts, parts[1:])):
                raise ValueError("Copied blocks would run together")
            answer = "".join(parts)
            if answer in {"".join(blocks) for blocks in candidates.values()}:
                raise ValueError("Use SELECT for a complete existing answer")
            result = Commit(answer, "COMMITTED", base_id, donor_id, replaced, copied)
        else:
            raise ValueError("Unknown operation or extra fields")
        if any(literal not in result.answer for literal in protected_literals):
            raise ValueError("Explicit protected literal was removed")
        return result
    except (ValueError, TypeError):
        return Commit(fallback_answer, "CONTRACT_FALLBACK", fallback)
