from .common import ROOT, canonical, token_estimate


ROLES = {"CURRENT_FACT", "HISTORICAL_FACT", "USER_PREFERENCE", "USER_BELIEF", "TASK_CONSTRAINT", "BACKGROUND_EVIDENCE"}
APPLICATIONS = {"APPLY", "PARTIAL_APPLY", "HISTORICAL_ONLY", "BACKGROUND_ONLY", "SUPPRESS_FOR_QUERY"}


def source_pack(store, candidates, budget=16000):
    selected, seen, total = [], set(), 0
    # Prefer directly retrieved sources and atomic records before broad summaries.
    ordered = sorted(enumerate(candidates), key=lambda x: (x[1].get("metadata", {}).get("semantic_type") == "summary", x[0]))
    for _, doc in ordered:
        for ref in doc["source_ids"]:
            source = store.source(ref)
            if not source or ref in seen:
                continue
            cost = token_estimate(canonical(source))
            if total + cost > budget:
                continue
            seen.add(ref)
            selected.append(source)
            total += cost
    return selected


class EvidenceCompiler:
    def __init__(self, gateway):
        self.gateway = gateway
        self.prompt = (ROOT / "prompts" / "evidence_compiler.md").read_text()

    def compile(self, task_needs, candidates, current_evidence, sources, key):
        mids = {d["id"] for d in candidates if d["kind"] == "memory"}
        by_source = {s["id"]: s for s in sources}
        need_ids = {n["id"] for n in task_needs["information_needs"]}

        def validate(obj):
            assert isinstance(obj["items"], list) and isinstance(obj["needs"], list)
            for item in obj["items"]:
                assert item["need_id"] in need_ids
                assert item["role"] in ROLES and item["application"] in APPLICATIONS
                assert set(item.get("memory_ids", [])) <= mids
                assert item["source_ids"] and set(item["source_ids"]) <= set(by_source)
                assert item["quote"] and any(item["quote"] in by_source[s]["content"] for s in item["source_ids"])
            assert {n["id"] for n in obj["needs"]} == need_ids
            assert all(n["status"] in ("SUPPORTED", "PARTIAL", "MISSING", "CONFLICTED") for n in obj["needs"])
            assert isinstance(obj.get("refinement", []), list) and len(obj.get("refinement", [])) <= 4
            assert all(a["action"] in ("RETRIEVE", "TRACE_SOURCE", "RESOLVE_VERSION", "REFINE_QUERY") for a in obj.get("refinement", []))
        return self.gateway.object(key, self.prompt, {"task_needs": task_needs, "candidates": candidates,
                                   "source_evidence": sources, "current_evidence": current_evidence}, validate, 8192)
