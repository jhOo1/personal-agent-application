"""Compile separate decision permissions and verbatim releases from frozen history."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SlotKind = Literal["decision", "expression", "fact"]
Mode = Literal["prefer", "require", "express", "ground"]
Exposure = Literal["binary", "raw", "partitioned"]


@dataclass(frozen=True)
class Slot:
    """A destination declared by a frame that only received the current task."""

    id: str
    kind: SlotKind
    description: str
    options: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Permission:
    """Use a source for a destination. Only ground releases an original span."""

    source: str
    slot: str
    mode: Mode
    option: str | None = None
    span: tuple[int, int] | None = None
    instruction: str | None = None


KINDS = {"prefer": "decision", "require": "decision", "express": "expression", "ground": "fact"}


def compile_release(
    slots: tuple[Slot, ...],
    sources: dict[str, str],
    permissions: tuple[Permission, ...],
    *,
    exposure: Exposure,
) -> dict:
    """Render a fixed authorization plan under one of two exposure regimes.

    The binary control exposes whole admitted records. The partitioned arm
    transmits declared task choices and exact released spans. This verifies the
    provenance of transmitted text, not the correctness of the authorization.
    """
    if exposure not in ("binary", "raw", "partitioned"):
        raise ValueError("Unknown exposure regime")
    by_slot = {s.id: s for s in slots}
    if len(by_slot) != len(slots):
        raise ValueError("Duplicate task slot")
    permitted_options = {}
    for slot in slots:
        options = dict(slot.options)
        if len(options) != len(slot.options) or slot.kind not in ("decision", "expression", "fact"):
            raise ValueError("Invalid task frame")
        if slot.kind == "fact" and options:
            raise ValueError("Fact slots accept grounded spans only")
        permitted_options[slot.id] = options

    accepted = set()
    released = []
    effects = []
    for permit in permissions:
        key = (permit.source, permit.slot, permit.mode, permit.option, permit.span, permit.instruction)
        if key in accepted:
            raise ValueError("Duplicate permission")
        accepted.add(key)
        slot = by_slot.get(permit.slot)
        if permit.source not in sources or slot is None or KINDS.get(permit.mode) != slot.kind:
            raise ValueError("Permission refers to an invalid source or destination")
        if permit.mode == "ground":
            span = permit.span
            if (permit.option is not None or permit.instruction is not None or span is None or len(span) != 2
                    or any(type(i) is not int for i in span)
                    or not 0 <= span[0] < span[1] <= len(sources[permit.source])):
                raise ValueError("Invalid exact fact span")
            quote = sources[permit.source][span[0]:span[1]]
            if not quote.strip():
                raise ValueError("Cannot release whitespace")
            released.append({"slot": slot.description, "text": quote})
        else:
            options = permitted_options[permit.slot]
            if permit.span is not None or (permit.option is None) == (permit.instruction is None):
                raise ValueError("Effect must supply one kind of action argument")
            if permit.instruction is not None:
                if not 1 <= len(permit.instruction.strip()) <= 240:
                    raise ValueError("Invalid derived action argument")
                if sources[permit.source].strip() in permit.instruction:
                    raise ValueError("Effect republishes its entire source record")
                value = permit.instruction
            else:
                if permit.option not in options:
                    raise ValueError("Effect refers to an invalid task-only choice")
                value = options[permit.option]
            effects.append({"slot": slot.description, "operation": permit.mode, "value": value})

    if exposure in ("binary", "raw"):
        admitted = {p.source for p in permissions}
        history = [text for key, text in sources.items() if key in admitted]
        return {"history": history} if exposure == "binary" else {"history": history, "decision_controls": effects}
    return {"grounded_facts": released, "decision_controls": effects}
