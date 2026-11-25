"""Reconstruct the archived Grounding and GEPA request contracts."""
import json

import run_qamc_persistbench_grounding_transfer as transfer

grounding, smoke = transfer.grounding, transfer.smoke


def input_requests(case, public, protocol):
    query, memories = public["query"], public["memories"]
    selector = transfer.read(smoke.base.PROMPTS)["selector"] + "\n\n" + smoke.STYLE_TRANSFER
    boundary = transfer.confirmation.route.PROMPT + "\n\n" + transfer.confirmation.routing.BOUNDARY
    payload = {"query": query, "memories": [
        {"id": f"M{i}", "text": text} for i, text in enumerate(memories, 1)
    ]}
    return {
        "query": smoke.job(protocol, case, "QUERY", "Actor", boundary,
                           json.dumps({"query": query}, ensure_ascii=False))["request"],
        "style": smoke.job(protocol, case, "STYLE", "Selector", selector,
                           json.dumps(smoke.task(case, public).payload(), ensure_ascii=False))["request"],
        "grounding": smoke.job(protocol, case, "GROUNDING", "Selector", grounding.PROMPTS["GROUNDING"],
                               json.dumps(payload, ensure_ascii=False))["request"],
    }


def select(case, public, route_reply, selector_reply):
    route = transfer.confirmation.route.decode(route_reply, public["query"])
    if route["check_history"]:
        return smoke.pick("STYLE", case, public, selector_reply)
    memories = public["memories"]
    ids = grounding.decode(selector_reply, len(memories))
    return [text for i, text in enumerate(memories, 1) if f"M{i}" in ids]


def actor_request(case, query, evidence, protocol, gepa):
    _, _, renderer = smoke.upstream()
    model = protocol["protocols"]["qwen"]["model"]
    system = renderer["build_generation_prompt"](evidence, model, gepa)
    return smoke.job(protocol, case, "SELECTED_GEPA", "Actor", system, query)["request"]


def check_archive(smoke_rows):
    first = transfer.read(transfer.OUT / "PLAN.json")
    factorial = transfer.read(transfer.ROOT / "reports/qamc_persistbench_actor_factorial/PLAN.json")
    count = 0
    for case in first["cases"]:
        uid = case["uid"]
        public = smoke.public(smoke_rows[case["line"] - 1])
        actual = input_requests(case, public, first)
        if any(actual[name] != first["jobs"][uid][name]["request"] for name in actual):
            raise ValueError("Historical selection request drift")
        actor = actor_request(case, public["query"], factorial["evidence"][uid],
                              factorial, factorial["prompts"]["gepa"])
        if actor != factorial["jobs"][uid]["SELECTED_GEPA"]["request"]:
            raise ValueError("Historical Actor request drift")
        count += 1
    return count


if __name__ == "__main__":
    smoke_rows = smoke.source()
    print(check_archive(smoke_rows))
