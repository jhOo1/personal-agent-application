"""Keep generated realizations of the same guarded decision consistent."""
import json

import beneficiary_ranking as rank


ORDINARY = "ORDINARY_COMPOSE"
OFF = "LINKS_OFF"
ON = "LINKS_ON"
MODES = (OFF, ON, ORDINARY)

ORDINARY_PROMPT = """Write the complete final answer in the language and format of the original task.
You have the actual task and facts, a preliminary task-only draft with optional textual alternatives,
and original evidence about prior preferences. Treat the draft as a useful starting point. Prefer a
clear and direct answer that preserves the task and helpful details. Use a preference when it improves
an existing choice or expresses a real requirement of the people affected by that choice. One person's
own constraint can matter for a shared result they actually use; organizing for someone else does not
transfer private tastes to that person. Preserve optionality of useful soft preferences. Keep actual
requirements consistent wherever they apply, including recommendations, examples and subsequent steps.
Avoid adding facts or goals. Where a candidate property requires verification, state the concrete
remaining check and give useful supported alternatives. Return only {"answer": "the final answer"}."""

LINKED_PROMPT = rank.HISTORY_PROMPT + """

The full task-only draft is supplied with stable block and option IDs. Return exactly the decisions
field described above, plus linked_prose. A decision is the choice being made. It can appear in
different language in several draft passages: a default, a backup, an example or a downstream step
such as booking. If a validated guard on a CHOICE changes what can be recommended, identify the
actual CONTENT spans that still contradict the same decision, weaken its required strength, or
instruct the reader to follow an option that no longer applies. Repair only those commitments.
Use the original task, the intended actor and the guard's original words; generic advice, discussion
of limitations, explicit avoidance and unrelated requirements remain as written. Keep task-supported
content in a partly affected span. For a property not established by the task or option design,
express what needs checking without claiming it is already satisfied. Do not reopen a known condition.

linked_prose is an array of at most 12 records:
{"prose":"D2","choice":"D3","old":"exact substring occurring once in D2","new":"local replacement"}.
An empty new string is allowed for a redundant sentence that exists only to recommend a discarded
option. Write replacements that read naturally in place. A repair must depend on the indicated
non-null guard and must not overlap other repairs. Unrelated prose should have no record. Do not link
merely because two blocks share a topic or mention the same word. Use [] when there is no required
change. Return one JSON object and no commentary."""


def request(root, blocks, arm):
    catalog = {}
    for slot, block in blocks.items():
        item = dict(block)
        if item["kind"] == "CHOICE":
            item["options"] = {f"O{i}": text for i, text in enumerate(item.pop("lines"), 1)}
        catalog[slot] = item
    payload = {"task": root["public_task"], "draft": catalog,
               "source_evidence": root["original_sources"]}
    return rank.planning.request(payload, ORDINARY_PROMPT if arm == ORDINARY else LINKED_PROMPT, 8192)


def ordinary_answer(raw):
    obj = rank.model_object(raw, "answer")
    if set(obj) != {"answer"} or not rank.planning.text(obj["answer"], 24000):
        raise ValueError("Invalid ordinary answer")
    return obj["answer"]


def compile_links(root, blocks, raw):
    obj = rank.model_object(raw, "decisions")
    if set(obj) != {"decisions", "linked_prose"}:
        raise ValueError("Invalid linked response")
    choices = {slot: block for slot, block in blocks.items() if block["kind"] == "CHOICE"}
    policy, rejected = rank.read_policy(root, choices, json.dumps({"decisions": obj["decisions"]}, ensure_ascii=False))
    content = {slot: block["lines"][0] for slot, block in blocks.items() if block["kind"] == "CONTENT"}
    linked, proposals = {}, obj["linked_prose"]
    if not isinstance(proposals, list) or len(proposals) > 12:
        return policy, linked, rejected + ["LINKS"]
    for entry in proposals:
        if not isinstance(entry, dict) or set(entry) != {"prose", "choice", "old", "new"}:
            rejected.append("LINK_FORMAT")
            continue
        prose, choice, old, new = (entry[key] for key in ("prose", "choice", "old", "new"))
        if (not isinstance(prose, str) or prose not in content or not isinstance(choice, str)
                or not policy.get(choice, {}).get("guard") or not rank.planning.text(old, 4200)
                or not isinstance(new, str) or len(new) > 2200 or old == new):
            rejected.append("LINK_SCOPE")
            continue
        start = content[prose].find(old)
        if start == -1 or content[prose].find(old, start + 1) != -1:
            rejected.append("LINK_SPAN")
            continue
        linked.setdefault(prose, []).append({**entry, "start": start, "end": start + len(old)})
    for prose, edits in list(linked.items()):
        edits.sort(key=lambda item: item["start"])
        if any(a["end"] > b["start"] for a, b in zip(edits, edits[1:])):
            rejected.append("LINK_OVERLAP")
            del linked[prose]
    return policy, linked, rejected


def render(root, blocks, policy, links):
    projected = {}
    for slot, block in blocks.items():
        if slot not in links:
            projected[slot] = block
            continue
        text = block["lines"][0]
        for edit in reversed(links[slot]):
            text = text[:edit["start"]] + edit["new"] + text[edit["end"]:]
        if text.strip():
            projected[slot] = {**block, "lines": [text]}
    return rank.render(root, projected, policy, rank.GENERIC)
