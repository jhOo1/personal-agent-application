"""Mechanical rejection of known dataset identities in deployable Policy content.

This cannot certify universal anonymity or semantic generality. Retained provenance
ids live in support_experience_ids and are never routed as narrative rule content.
"""
import re
from qamc.common import canonical


def guard(cards,identities,queries):
    text=canonical([{k:c[k]for k in ['trigger','positive_use','boundary','exceptions','evidence_pattern']}for c in cards]).casefold()
    if re.search(r'\bh\d+@\d+:\d+:[0-9a-f]{8}\b|\braw:h\d+:\d+\b|\bh\d{3,6}\b|\bu\d{1,6}\b|\bq0\b',text):
        raise ValueError('specific source locator in generic policy content')
    for identity in identities:
        name=identity.strip().casefold()
        if name not in {'user','assistant','group','unknown','self','other','world'}and len(name)>=5 and name in text:
            raise ValueError('known user identity in policy content')
    for query in queries:
        for i in range(max(0,len(query)-59)):
            if query[i:i+60].casefold()in text:raise ValueError('long query/option excerpt in policy content')
    return cards
