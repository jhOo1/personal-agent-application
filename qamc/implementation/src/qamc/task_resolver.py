from .common import ROOT


class TaskResolver:
    def __init__(self, gateway):
        self.gateway = gateway
        self.prompt = (ROOT / "prompts" / "task_resolver.md").read_text()

    def parse(self, query, context, query_time, key):
        def validate(obj):
            assert obj["goal"] and isinstance(obj["information_needs"], list)
            assert obj["information_needs"] and len({x["id"] for x in obj["information_needs"]}) == len(obj["information_needs"])
            assert obj["time_mode"] in ("current", "historical", "change", "unspecified")
            assert isinstance(obj["search_queries"], list) and 1 <= len(obj["search_queries"]) <= 4
            assert all(isinstance(q, str) and q.strip() for q in obj["search_queries"])
            assert isinstance(obj.get("scope", {}), dict)
        return self.gateway.object(key + "/resolve", self.prompt,
                                   {"query": query, "current_context": context, "query_time": query_time}, validate)
