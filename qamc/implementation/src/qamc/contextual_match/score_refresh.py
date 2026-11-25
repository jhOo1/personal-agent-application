"""Permit explicit late scoring without changing a saved generation experiment."""
from copy import deepcopy

SCORING_FIELDS={'score','raw_scores','judge_statuses','score_error_type','score_error'}


def verify_refresh(original,updated):
    if original['wave']!=updated['wave'] or original['representations']!=updated['representations']:
        raise ValueError('Representation or wave identity changed during score-only refresh')
    before={(r['uid'],r['method']):r for r in original['rows']}
    after={(r['uid'],r['method']):r for r in updated['rows']}
    if before.keys()!=after.keys():raise ValueError('Generation coverage changed during score-only refresh')
    for key,old in before.items():
        new=after[key]
        public_generation=lambda r:{k:v for k,v in r.items() if k not in SCORING_FIELDS}
        if public_generation(old)!=public_generation(new):raise ValueError('Saved answer/Actor input changed during score-only refresh')
        if old.get('score') is not None and any(old.get(k)!=new.get(k) for k in SCORING_FIELDS):
            raise ValueError('Previously valid score was replaced')
    return deepcopy(updated)
