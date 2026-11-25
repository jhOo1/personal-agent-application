"""Policy content views without identity/version noise in model-visible text.

Library-version hashes remain in durable keys and traces. The online input hash
represents only cards actually routed to that role, preserving opposite-role
inputs and exact reuse when a changed card is not selected.
"""
from qamc.common import sha,canonical

CONTENT_KEYS=('trigger','positive_use','boundary','exceptions','evidence_pattern')


def content(card):return {k:card[k]for k in CONTENT_KEYS}


def fingerprint(cards):
    def normalized(x):
        if isinstance(x,str):return ' '.join(x.split())
        if isinstance(x,list):return [normalized(v)for v in x]
        if isinstance(x,dict):return {k:normalized(v)for k,v in x.items()}
        return x
    views={role:sorted({canonical(normalized(content(c)))for c in cards if c['target_role']in {role,'both'} and c.get('status','active')=='active'})for role in ['allow','deny']}
    return sha(views)


def role_hash(cards):return sha(cards)


def joint_hash(allow,deny):
    # Preserve the exact empty-library baseline interface for success-cache reuse.
    return sha({'allow':allow,'deny':deny})if allow or deny else sha([])
