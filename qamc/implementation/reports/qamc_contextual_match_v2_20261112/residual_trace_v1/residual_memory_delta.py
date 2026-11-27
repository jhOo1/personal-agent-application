"""Identify and replay a single change to an existing Actor's memory state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Entry:
    source: str
    use: str | None = None


@dataclass(frozen=True)
class Delta:
    operation: Literal["KEEP", "ADD", "REMOVE", "REBIND"]
    source: str | None = None
    use: str | None = None


def index_state(candidate_order, state):
    positions = {source: i for i, source in enumerate(candidate_order)}
    if len(positions) != len(candidate_order):
        raise ValueError("Repeated original candidate identity")
    entries = {entry.source: entry for entry in state}
    ids = tuple(entries)
    if len(entries) != len(state) or not entries.keys() <= positions.keys():
        raise ValueError("Memory state contains an unknown or repeated source")
    if ids != tuple(sorted(ids, key=positions.__getitem__)):
        raise ValueError("Memory state does not preserve candidate order")
    return entries


def apply(candidate_order, state, delta, *, allowed_usage=None):
    """Modify one original source. The adapter separately freezes task and Actor."""
    entries = index_state(candidate_order, state)
    if delta.operation == "KEEP":
        if delta.source is not None or delta.use is not None:
            raise ValueError("KEEP needs no arguments")
        return tuple(state)
    if delta.source not in candidate_order:
        raise ValueError("Unknown original source")
    if delta.operation == "REMOVE":
        if delta.source not in entries or delta.use is not None:
            raise ValueError("REMOVE requires one selected source")
        del entries[delta.source]
    elif delta.operation in ("ADD", "REBIND"):
        if (delta.operation == "REBIND") != (delta.source in entries):
            raise ValueError("ADD requires absence and REBIND requires presence")
        if allowed_usage is not None and delta.use not in allowed_usage:
            raise ValueError("Policy outside the original Actor contract")
        if delta.operation == "REBIND" and entries[delta.source].use == delta.use:
            raise ValueError("REBIND would not change use")
        entries[delta.source] = Entry(delta.source, delta.use)
    else:
        raise ValueError("Invalid residual operation")
    return tuple(entries[s] for s in candidate_order if s in entries)


def difference(candidate_order, before, after):
    """Return the verified single operation, or None for composite changes."""
    left = index_state(candidate_order, before)
    right = index_state(candidate_order, after)
    touched = [s for s in candidate_order if left.get(s) != right.get(s)]
    if len(touched) > 1:
        return None
    if not touched:
        return Delta("KEEP")
    source, = touched
    if source not in left:
        return Delta("ADD", source, right[source].use)
    if source not in right:
        return Delta("REMOVE", source)
    return Delta("REBIND", source, right[source].use)
