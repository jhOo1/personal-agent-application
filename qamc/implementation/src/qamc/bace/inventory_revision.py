"""Offline candidate: interleave source-backed task and preference uses.

Not wired into the frozen live engine. This allocation prevents one predicted
category from occupying every slot; it does not certify necessity or relevance.
"""
from .contract import UseKey
from .coverage import PREFERENCE_USES


def interleaved_inventory(allow, deny, required=(), maximum=12):
    if type(maximum) is not int or maximum < 1:
        raise ValueError('Positive integer cap required')
    required = set(required)
    keys = set(allow) | set(deny) | required
    if any(not isinstance(k, UseKey) for k in keys):
        raise ValueError('Normalized UseKeys required')
    # Keep the original stable ordering within each channel. No model scores,
    # reference labels, answer choices, or new retrieval inform allocation.
    ordered = sorted(keys, key=lambda k: (k not in required, k))
    facts = [k for k in ordered if k.use_kind not in PREFERENCE_USES]
    preferences = [k for k in ordered if k.use_kind in PREFERENCE_USES]
    mixed = []
    for i in range(max(len(facts), len(preferences))):
        if i < len(facts):
            mixed.append(facts[i])
        if i < len(preferences):
            mixed.append(preferences[i])
    # Overflow remains explicitly unassessed, including necessary-fact claims.
    return {'selected': mixed[:maximum],
            'unassessed_overflow': mixed[maximum:],
            'required_overflow': [k for k in mixed[maximum:] if k in required]}
