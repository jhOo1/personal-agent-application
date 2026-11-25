"""Offline evolution extension boundary; no parameter updates or answer-to-memory writes."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class FeedbackTrace:
    question_id: str
    version: str
    source_ids: tuple[str, ...]
    memory_ids: tuple[str, ...]
    retrieval_rounds: int
    outcome: dict = field(default_factory=dict)


class OfflineEvolutionHook(Protocol):
    def propose_revision(self, traces: list[FeedbackTrace]) -> dict:
        """Return a reviewable config proposal; never mutate the live store or weights."""
        ...
