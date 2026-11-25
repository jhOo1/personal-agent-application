"""Construct shared source-level demonstrations from disjoint development groups."""
import json

from freeze_recovery_challenge import HERE, OUT
from incremental_decision import selector_messages
from incremental_panel import LOCAL, prior, read, sha


def demonstrations():
    held = {row["group"] for row in read(OUT)}
    frozen = read(prior.R["archived"].v41.OUT / "FROZEN.json")
    if frozen["independent_confirmation"]:
        raise ValueError("Expected exposed development archive")
    roots = {row["uid"]: row for row in frozen["roots"]}
    ranked = []
    for pair in read(LOCAL / "ELIGIBILITY.json")["pairs"]:
        if pair["group"] in held:
            raise ValueError("Demonstration overlaps challenge group")
        choices = {role: [] for role in ("all_A", "B_only")}
        for endpoint in pair["endpoints"]:
            labels = endpoint["labels"]
            if set(labels) - set("AB") or not labels:
                continue
            role = "B_only" if "B" in labels else "all_A"
            choices[role].append(endpoint)
        if all(choices.values()):
            ranked.append((sha(["recovery-demonstrations", pair["group"]]), choices))
    examples = []
    for _, pair in sorted(ranked)[:2]:
        for role in ("all_A", "B_only"):
            endpoint = min(pair[role], key=lambda row: sha(row["uid"]))
            root = roots[endpoint["uid"]]
            sources = root["original_sources"]
            if sources != endpoint["sources"] or len(sources) != len(endpoint["labels"]):
                raise ValueError("Demonstration source alignment changed")
            candidates = {source["memory_id"]: source["text"] for source in sources}
            suitable = [source["memory_id"] for source, label in
                        zip(sources, endpoint["labels"], strict=True) if label == "B"]
            examples.append({"task": root["public_task"], "sources": candidates,
                             "applicable_soft_sources": suitable})
    if len(examples) != 4:
        raise ValueError("Missing balanced development demonstrations")
    return examples


def messages(task, anchor, sources, examples, *, incremental):
    messages = selector_messages(json.dumps(task, ensure_ascii=False), anchor, sources,
                                 incremental=incremental)
    messages[0]["content"] += (
        "\nThe examples only illustrate context-dependent applicability. Their candidate IDs "
        "are local to each example. Decide the current case from its own inputs."
    )
    messages[1]["content"] = json.dumps(
        {"development_examples": examples,
         "current_case": {"task": task, "task_only_answer": anchor, "sources": sources}},
        ensure_ascii=False,
    )
    return messages


if __name__ == "__main__":
    from recovery_challenge_inputs import prepare
    from proposals.qamc_protocol_alignment.transport import canonical, token_estimate

    examples = demonstrations()
    lengths = []
    for case in prepare().values():
        wires = [messages(case["task"], case["anchor"], case["sources"], examples,
                          incremental=flag) for flag in (False, True)]
        if wires[0][1] != wires[1][1]:
            raise ValueError("Unequal supervision")
        lengths.extend(token_estimate(canonical(wire)) for wire in wires)
    if max(lengths) > 32768:
        raise ValueError("Prompt exceeds capacity")
    print(len(examples), len(lengths), max(lengths))
