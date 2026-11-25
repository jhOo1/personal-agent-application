"""Carry exact free text outside transaction metadata without editing its meaning."""
import json
import re

from qamc.common import sha

import decision_transactions as core


METADATA_EXAMPLE = """{"decisions":[{"decision":"T1","task_basis":"T2",
  "effects":[{"id":"E1","source":{"id":"M0","quote":"T3"},
              "site":"SHARED_OUTCOME","authority":"SELF","force":"REQUIRE","delegation":null}],
  "variants":[{"effects":["E1"],"patches":[{"block":"D1","option":null,
                   "before":"T4","after":"T5"}]}]}]}"""
BODY_RULES = """Return the metadata JSON first, with no preface or fences. In the metadata, use a
text reference T1, T2, etc. for EVERY decision, task_basis, source.quote, non-null delegation,
before, and after field. Then provide each referenced text exactly once in a separate block.
Its header is on a line by itself, with the marker followed by a space and the exact reference.
Preserve the unescaped original text inside the block, including quotation marks, backslashes,
spaces and line breaks. Use an empty block for an empty replacement. Reuse a reference for
identical passages if useful. End with the marker followed by a space and END alone on its line.
The next marker line ends the previous block. Do not put any other text outside the format.
At most 8 decisions, 8 effects and 3 variants per decision, and 8 patches per variant.
Reuse each effect ID in all variants using that proposition. Before must occur once inside the
specified block and option; use null option for CONTENT. Keep all spans non-overlapping within
a variant and between decisions. A variant must genuinely change the text. Use an empty after
only to remove redundant text. With no change, output {"decisions":[]} then the END line."""


def packet_marker(user_content):
    # A marker inside source data could split a legitimate verbatim field.
    # Derive the marker from the complete public packet and avoid that case.
    prefix = "@@QAMC-" + sha(user_content)[:12]
    while prefix in user_content:
        prefix += "X"
    return prefix


def request(root, blocks, arm):
    if arm == core.ORDINARY:
        wire = core.linked.request(root, blocks, arm)
        prompt = wire["messages"][0]["content"]
        suffix = ' Return only {"answer": "the final answer"}.'
        if not prompt.endswith(suffix):
            raise ValueError("The ordinary comparison prompt changed")
        wire["messages"][0]["content"] = prompt.removesuffix(suffix) + " Return only the final answer as plain text."
        return wire

    wire = core.request(root, blocks)
    semantics, _, _ = core.PROMPT.partition("\nReturn exactly this JSON shape.")
    if semantics == core.PROMPT:
        raise ValueError("The transaction prompt changed")
    prefix = packet_marker(wire["messages"][1]["content"])
    wire["messages"][0]["content"] = f"""{semantics}

{BODY_RULES}
Your marker is {prefix}.
Example format, with placeholders replaced by actual source and draft excerpts:
{METADATA_EXAMPLE}
{prefix} T1
the existing task choice
{prefix} T2
exact task excerpt
{prefix} T3
exact source excerpt
{prefix} T4
unique original text
{prefix} T5
replacement with ordinary "quotes" if needed
{prefix} END"""
    return wire


def transform_text(metadata, convert):
    decisions = []
    for unit in metadata["decisions"]:
        effects = [{**effect, "source": {**effect["source"], "quote": convert(effect["source"]["quote"])},
                    "delegation": convert(effect["delegation"]) if effect["delegation"] is not None else None}
                   for effect in unit["effects"]]
        variants = [{**variant, "patches": [{**patch, "before": convert(patch["before"]),
                                             "after": convert(patch["after"])} for patch in variant["patches"]]}
                    for variant in unit["variants"]]
        decisions.append({**unit, "decision": convert(unit["decision"]), "task_basis": convert(unit["task_basis"]),
                          "effects": effects, "variants": variants})
    return {**metadata, "decisions": decisions}


def encode(metadata, prefix):
    """Encode archival valid objects as fixtures for byte-level codec tests."""
    references = {}

    def reference(text):
        if not isinstance(text, str) or prefix in text:
            raise ValueError("Text field collides with the response marker")
        return references.setdefault(text, f"T{len(references) + 1}")

    compact = transform_text(metadata, reference)
    body = [json.dumps(compact, ensure_ascii=False)]
    body.extend(f"{prefix} {ref}\n{text}" for text, ref in references.items())
    body.append(f"{prefix} END")
    return "\n".join(body)


def decode(raw, prefix):
    if not isinstance(raw, str):
        raise ValueError("Missing transaction response")
    pattern = re.compile(r"^" + re.escape(prefix) + r" (T[1-9][0-9]*|END)(?:\n|\Z)", re.MULTILINE)
    markers = list(pattern.finditer(raw))
    if not markers or markers[-1][1] != "END" or raw[markers[-1].end():].strip():
        raise ValueError("Missing or misplaced transaction end marker")
    fields = {}
    for start, end in zip(markers, markers[1:]):
        ref = start[1]
        if ref == "END" or ref in fields:
            raise ValueError("Duplicate transaction field marker")
        text = raw[start.end():end.start()].removesuffix("\n")
        if prefix in text:
            raise ValueError("Transaction marker inside text field")
        fields[ref] = text
    used = set()

    def resolve(ref):
        if not isinstance(ref, str) or ref not in fields:
            raise ValueError("Missing or invalid transaction text reference")
        used.add(ref)
        return fields[ref]

    metadata = core.rank.draft.read_object(raw[:markers[0].start()])
    result = transform_text(metadata, resolve)
    if used != fields.keys():
        raise ValueError("Unreferenced transaction text block")
    return result


def ordinary_answer(raw):
    if not core.rank.planning.text(raw, 24000):
        raise ValueError("Missing or oversized ordinary text")
    return raw
