from .common import ROOT


class Actor:
    def __init__(self, gateway):
        self.gateway = gateway
        self.prompt = (ROOT / "prompts" / "actor.md").read_text()

    def generate(self, query, context, evidence_view, key, query_time=None):
        return self.gateway.complete(key, self.prompt, {"query": query, "context": context,
                                     "query_time": query_time, "memory_view": evidence_view}, 4096)
