"""A conservative task-level veto based on disagreement about topical sources."""
import re
import unicodedata
from fractions import Fraction


def bigrams(text):
    chars = "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())
    return {chars[i:i + 2] for i in range(len(chars) - 1)}


def overlap(query, text):
    utterances = re.split(r"(?:^|\n)\s*(用户|助手)\s*[：:]", text)
    snippets = ([text] if len(utterances) == 1 else
                [body for role, body in zip(utterances[1::2], utterances[2::2]) if role == "用户"])
    best = Fraction(0)
    for snippet in snippets:
        terms = bigrams(snippet)
        if query and terms:
            best = max(best, Fraction(len(query & terms), len(query | terms)))
    return best


def veto(query, sources, policy, rotate=False):
    tags = {p["memory_id"]: p["policy"] for p in policy}
    ids = [s["memory_id"] for s in sources]
    if len(tags) != len(ids) or set(ids) != set(tags) or not ids:
        raise ValueError("Unaligned source and RP policy")
    scores = [overlap(bigrams(query), s["text"]) for s in sources]
    best = max(scores)
    winners = [k for k, score in enumerate(scores) if score == best]
    return bool(best and all(tags[ids[(k + int(rotate)) % len(ids)]] == "A" for k in winners))
