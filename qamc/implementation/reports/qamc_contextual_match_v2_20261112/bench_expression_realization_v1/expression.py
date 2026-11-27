"""Locate and replace editable sentence spans inside a frozen message."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re


WORD = re.compile(r"\b[\w]+(?:['’\-][\w]+)*\b")
BREAK = re.compile(r"[.!?](?:\*\*)?(?=\s+\S)")
MARKUP = re.compile(r"[*_`#\[\]<>@]|https?://")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
HEADER = re.compile(r"^\s*(?:subject\s*:|dear\b|hi\b|hello\b|to\s*:|re\s*:|from\s*:|date\s*:)", re.I)
INLINE_GREETING = re.compile(r"^(?:Dear|Hi|Hello)\s+[^,.!:]{1,70},\s+(?=[A-Z])")
CLOSE = re.compile(r"^\s*(?:sincerely|kind regards|best regards|best wishes|best|regards|respectfully|warm regards|many thanks)[,.!]?\s*$", re.I)
OPTIONAL = re.compile(r"\b(?:not|never|no|none|without|unless|if|only|except|may|might|must|could|cannot|can't|won't|should|need to|required)\b", re.I)
AMOUNT = re.compile(r"(?:[$€£]\s*)?\d[\w,./:%\-]*")
CAPITAL = re.compile(r"\b[A-Z][\w'’\-]*\b")
ABBREVIATION = re.compile(r"(?:\b(?:Mr|Mrs|Ms|Dr|St|Sr|Jr|vs|etc|Inc|Ltd|No)\.|\b(?:[A-Z]\.){1,})$", re.I)
EXPLICIT_STYLE = re.compile(r"\b(?:detailed|in detail|comprehensive|exhaustive|step[- ]by[- ]step|verbatim)\b", re.I)
BREVITY = re.compile(r"\b(?:prefer(?:s|red)?|likes?|wants?)\b[^.?!\n]{0,50}"
                     r"\b(?:short|simple|concise|brief|succinct)\b[^.?!\n]{0,36}"
                     r"\b(?:answers?|responses?|messages?|communication|replies|explanations?|language)\b", re.I)


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


def eligible(query, selected_sources):
    return not EXPLICIT_STYLE.search(query) and any(BREVITY.search(s) for s in selected_sources)


def locate(draft, limit=4):
    spans = []
    offset = 0
    for line in draft.splitlines(keepends=True):
        trimmed = line.strip()
        if CLOSE.fullmatch(trimmed):
            break
        greeting = INLINE_GREETING.match(trimmed)
        if trimmed and (greeting or not HEADER.match(line)) and not re.match(r"^\s*(?:[-•]|\d+[.)])\s+", line):
            line_start = offset + len(line) - len(line.lstrip())
            if greeting:
                line_start += greeting.end()
                trimmed = trimmed[greeting.end():]
            starts = [0]
            starts.extend(m.end() for m in BREAK.finditer(trimmed)
                          if not ABBREVIATION.search(trimmed[:m.end()]))
            for a, b in zip(starts, starts[1:] + [len(trimmed)], strict=True):
                # Preserve original separators and whitespace byte for byte.
                fragment = trimmed[a:b]
                s = line_start + a + len(fragment) - len(fragment.lstrip())
                excerpt = fragment.strip()
                plain = plain_text(excerpt)
                if (len(WORD.findall(plain)) >= 9 and plain.endswith((".", "!", "?"))
                        and not MARKUP.search(plain) and not BOLD.fullmatch(excerpt)):
                    spans.append(Span(s, s + len(excerpt), excerpt))
        offset += len(line)
    ordered = sorted(spans, key=lambda s: (-len(WORD.findall(s.text)), s.start))[:limit]
    return tuple(sorted(ordered, key=lambda s: s.start))


def anchors(text):
    caps = [m.group() for m in CAPITAL.finditer(text) if m.start() > 0 or m.group().isupper() and m.group() != "I"]
    return tuple(Counter(parts) for parts in (caps, AMOUNT.findall(text),
                                               (m.group().casefold() for m in OPTIONAL.finditer(text))))


def plain_text(text):
    return BOLD.sub(r"\1", text)


def restore_format(old, candidate):
    if not isinstance(candidate, str) or MARKUP.search(candidate):
        return None
    positions = []
    for match in BOLD.finditer(old):
        plain = match.group(1)
        if candidate.count(plain) != 1:
            return None
        start = candidate.index(plain)
        positions.append((start, start + len(plain), match.group()))
    if any(a[1] > b[0] for a, b in zip(positions, positions[1:])):
        return None
    for start, end, text in reversed(positions):
        candidate = candidate[:start] + text + candidate[end:]
    return candidate


def valid_replacement(old, new):
    return (isinstance(new, str) and new == new.strip() and bool(new)
            and not MARKUP.search(plain_text(new)) and "\n" not in new and "\r" not in new
            and BOLD.findall(old) == BOLD.findall(new)
            and plain_text(new)[-1] == plain_text(old)[-1]
            and len(new) <= len(old) - 8 and len(WORD.findall(new)) < len(WORD.findall(old))
            and anchors(old) == anchors(new))


def apply(draft, spans, replacements):
    if len(spans) != len(replacements):
        raise ValueError("Every candidate must have a unique original slot")
    result = draft
    previous = len(draft)
    for span, new in reversed(tuple(zip(spans, replacements, strict=True))):
        if not 0 <= span.start < span.end <= previous or draft[span.start:span.end] != span.text:
            raise ValueError("Original edit span is invalid or overlaps")
        if new is not None:
            if not valid_replacement(span.text, new):
                raise ValueError("Replacement bypasses immutable-field contract")
            result = result[:span.start] + new + result[span.end:]
        previous = span.start
    return result
