"""A sparse union preserves unassessed and overflow identities explicitly."""
from .contract import UseKey


def union_inventory(allow, deny, required=(), maximum=12):
    if maximum < 1:
        raise ValueError('Positive frozen inventory cap required')
    required = set(required)
    all_keys = set(allow) | set(deny) | required
    if any(not isinstance(k,UseKey) for k in all_keys):
        raise ValueError('Inventory requires normalized UseKeys')
    # Required uses precede optional uses; otherwise stable key order, no Gold.
    ordered = sorted(all_keys,key=lambda k:(k not in required,k))
    return {'selected':ordered[:maximum], 'unassessed_overflow':ordered[maximum:],
            'required_overflow':[k for k in ordered[maximum:] if k in required]}
