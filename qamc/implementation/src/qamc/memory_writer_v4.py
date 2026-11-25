"""Versioned writer policy; ingestion and durable store mechanics are unchanged."""
from .common import ROOT
from .memory_writer import MemoryWriter, validate_writer_plan


class MemoryWriterV4(MemoryWriter):
    def __init__(self, gateway, retriever):
        super().__init__(gateway, retriever)
        self.prompt = (ROOT / "prompts/memory_writer_v4.md").read_text()

    def validate_plan(self, obj, allowed_sources, prior_records):
        validate_writer_plan(obj, allowed_sources, prior_records, strict_state_scope=True)
