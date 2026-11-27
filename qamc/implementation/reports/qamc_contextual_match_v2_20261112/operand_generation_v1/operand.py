"""Render a bounded decision operation without a downstream free-text writer."""
import re

from assembler import appears
from delta import decode, index


QUESTIONS = {
    "RECORD": ("Could you identify the relevant record or notice and the period it concerns?", "请问具体涉及哪条记录、哪一时间段？"),
    "DOCUMENTS": ("Please let me know which documents or information you need from me.", "请告知需要我提供哪些文件或信息。"),
    "OPTIONS": ("Could you outline the available options, eligibility, and any important terms?", "能否说明可选方案、适用条件及主要要求？"),
    "APPOINTMENT": ("Please let me know the available times and any preparation required.", "请告知可预约的时间及需要提前准备的事项。"),
    "NEXT_STEP": ("Please advise on the next step and whether I need to provide anything further.", "请告知下一步安排及是否需要我补充资料。"),
    "VERIFY": ("Could you confirm the relevant details before we proceed?", "可否先确认相关细节，再继续办理？"),
}
# These are single noun-phrase slots; the program supplies scope and punctuation.
LABEL = re.compile(r"[\w][\w \-’'·]{1,47}", re.UNICODE)
ASSERTION = re.compile(
    r"\b(?:requires?|must|because|guarantees?|available|certified|is|are|can|have|has|will)\b|"
    r"必须|保证|因为|全部|所有人|已确认|我曾|每人|建议大家", re.I)
SIGNOFF = re.compile(r"^(?:\*\*)?(?:Dear |To:|Sincerely[,\s]|Respectfully[,\s]|Best regards[,\s]|你好|您好|此致|敬礼)", re.I)
LIST_MARK = re.compile(r"^\s*(?:[-+*]|\d+[.)、])\s+")
KNOWN_SOURCE = re.compile(r"^[A-Z][0-9]+$")


def editable(unit):
    text = unit["text"].strip()
    return (unit["kind"] != "fixed" and bool(text)
            and not SIGNOFF.match(text) and not any(SIGNOFF.match(line.strip()) for line in text.splitlines()))


def render(public, changes):
    original = public["draft_units"]
    units = {row["id"]: row for row in original}
    language = 1 if re.search(r"[\u3400-\u9fff]", public["task"]["query"]) else 0
    edits = {}
    for action in changes:
        if not isinstance(action, dict):
            raise ValueError("Invalid operation")
        kind, target = action.get("op"), action.get("target")
        if not isinstance(target, str) or target not in units or target in edits or not editable(units[target]):
            raise ValueError("Target not available for operation")
        old = units[target]["text"]
        body = old.rstrip()
        trailing = old[len(body):]
        fields = set(action)
        if fields == {"op", "target"} and kind == "TRIM":
            edits[target] = ""
            continue
        if fields == {"op", "target", "dimensions"} and kind == "ASK_OPEN":
            dimensions = action["dimensions"]
            if (not isinstance(dimensions, list) or not 1 <= len(dimensions) <= 2
                    or any(not isinstance(k, str) or k not in QUESTIONS for k in dimensions)
                    or len(set(dimensions)) != len(dimensions)):
                raise ValueError("Unknown or duplicated question dimension")
            replacement = " ".join(QUESTIONS[key][language] for key in dimensions)
        elif fields == {"op", "target", "fact_id"} and kind == "REPORT_EVENT":
            key = action["fact_id"]
            facts = public["fact_operands"]
            if not isinstance(key, str) or not KNOWN_SOURCE.fullmatch(key) or key not in facts:
                raise ValueError("Unknown event source")
            span = facts[key]
            if not (12 <= len(span) <= 360) or "\n" in span:
                raise ValueError("Event requires one complete cited original entry")
            replacement = f"我的记录中写有：“{span}”" if language else f'My records note: “{span}”'
        elif fields == {"op", "target", "choice", "evidence"} and kind == "OFFER_ALTERNATIVE":
            label, key = action["choice"], action["evidence"]
            if (not isinstance(label, str) or not LABEL.fullmatch(label) or ASSERTION.search(label)
                    or not isinstance(key, str) or key not in public["offer_operands"]):
                raise ValueError("Alternative requires an available source and a short choice name")
            if label.casefold() in "".join(u["text"] for u in original).casefold():
                raise ValueError("Choice already occurs in draft")
            suffix = f"另一个可选方案是**{label}**，原有选项也保留。" if language else (
                f"An additional option is **{label}**. The other choices remain available.")
            edits[target] = body + "\n\n" + suffix + (trailing or "\n")
            continue
        else:
            raise ValueError("No arbitrary rewrite operation")
        prefix = LIST_MARK.match(body)
        edits[target] = (prefix[0] if prefix else "") + replacement + (trailing or " ")
    revised = "".join(edits.get(row["id"], row["text"]) for row in original)
    if not revised.strip():
        raise ValueError("Empty deliverable")
    return revised


def revise(answer, packet, arm):
    initial = "".join(row["text"] for row in packet["draft_units"])
    reply = decode(answer)
    if reply == {"mode": "KEEP"}:
        return initial, []
    if arm == "FREE":
        content = reply.get("answer")
        if set(reply) != {"mode", "answer"} or reply["mode"] != "REWRITE" or not isinstance(content, str) or not content.strip():
            raise ValueError("Unusable free answer")
        edited, operations = content, ["FREE"]
    else:
        changes = reply.get("actions")
        if set(reply) != {"mode", "actions"} or reply["mode"] != "OPERATE" or not isinstance(changes, list) or not 1 <= len(changes) <= 5:
            raise ValueError("Expected a bounded list of actions")
        edited = render(packet, changes)
        operations = [entry["op"] for entry in changes]
    if any(not appears(row["literal"], edited) for row in packet["protected_literals"]):
        raise ValueError("Protected task literal disappeared")
    return edited, operations
