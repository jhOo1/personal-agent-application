"""Attribute review excerpts after decoding explicit omissions and Markdown."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

from qamc.common import parse_object

RUN = Path("runs/qamc_contextual_match_v2_20261112/persist_frozen_utility_review_v1")
FIELDS = ("necessary", "deliverable", "optional_preference", "factual_reliability")
STATES = {"MET", "VIOLATED", "UNCERTAIN", "NOT_APPLICABLE"}


def normalized(text):
    # Presentation only. Preserve case, hyphens, words and punctuation.
    text = text.replace("**", "").replace("|", " ")
    text = re.sub(r"(?m)^\s*#{1,6} +", "", text)
    return " ".join(text.split())


def attribution(quote, answer):
    if not quote:
        return "NO_QUOTE"
    if quote in answer:
        return "EXACT"
    chunks = [normalized(x) for x in re.split(r"\.{3}|…", quote)]
    surface = normalized(answer)
    offset = 0
    for chunk in chunks:
        if not chunk:
            continue
        pos = surface.find(chunk, offset)
        if pos < 0:
            return "UNBOUND"
        offset = pos + len(chunk)
    return "PRESENTATION_OR_ELISION" if offset > 0 else "UNBOUND"


def audit(reviews, packet, mapping):
    pairs, evidence = defaultdict(dict), Counter()
    for identifier, row in reviews.items():
        receipt = row["receipt"]
        record = {}
        if receipt["status"] == "OK":
            try:
                raw = parse_object(receipt["answer"])
            except ValueError:
                raw = {}
            for field in FIELDS:
                v = raw.get(field)
                if (not isinstance(v, dict) or v.keys() != {"status", "quote", "reason"}
                        or v["status"] not in STATES or not isinstance(v["quote"], str)
                        or not isinstance(v["reason"], str) or not v["reason"].strip()):
                    continue
                quote_type = attribution(v["quote"], packet[identifier]["answer"])
                evidence[quote_type] += 1
                if quote_type == "UNBOUND" or (field in ("necessary", "deliverable") and (
                        v["status"] == "NOT_APPLICABLE"
                        or (v["status"] == "MET" and quote_type == "NO_QUOTE"))):
                    continue
                record[field] = v["status"]
        for ref in mapping[identifier]:
            pairs[ref["uid"]][ref["arm"]] = record
    fields = {}
    for field in FIELDS:
        fields[field] = Counter(
            f"{pair['ROUTED'].get(field, 'UNAVAILABLE')}/{pair['FULL'].get(field, 'UNAVAILABLE')}"
            for pair in pairs.values())
    return {
        "quote_checks": evidence,
        "paired_diagnostic_status_routed_then_full": fields,
        "fully_usable_diagnostic_pairs": sum(
            all(set(v) == set(FIELDS) for v in p.values()) for p in pairs.values()),
        "post_hoc_diagnostic": True,
    }


if __name__ == "__main__":
    root = RUN.with_name(RUN.name + sys.argv[1])
    read = lambda p: json.loads(p.read_text())
    result = audit(read(root / "RESULTS.json")["reviews"], read(RUN / "PRIVATE_PACKET.json"),
                   read(root / "PRIVATE_MAPPING.json"))
    print(json.dumps(result, sort_keys=True, indent=2))
