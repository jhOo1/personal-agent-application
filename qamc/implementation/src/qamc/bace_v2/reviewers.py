"""Explicit qualitative review states; calibration is not an execution gate."""
import math
from .use_inventory import validate_complete_assessment

FINDINGS = {'allow': {'SUPPORTED', 'NO_VALUE', 'UNCERTAIN', 'UNASSESSED'},
            'deny': {'ISSUE_FOUND', 'NO_ISSUE_FOUND', 'UNCERTAIN', 'UNASSESSED'}}
ISSUES = {'WRONG_SUBJECT_OR_RECIPIENT', 'CURRENT_REQUIREMENT_CONFLICT',
          'CONTEXTUAL_MISFIT', 'BELIEF_AS_WORLD_FACT', 'STATE_OR_TIME_ERROR',
          'UNNECESSARY_DISCLOSURE', 'OVEREXTENDED_INFLUENCE'}


def validate_reviews(rows, cards, role, allowed_refs):
    validate_complete_assessment(cards, rows)
    for row in rows:
        if set(row) != {'use_id', 'finding', 'refs', 'reason', 'raw_score', 'uncertainty', 'issue_type'}:
            raise ValueError('Review schema mismatch')
        if row['finding'] not in FINDINGS[role]:
            raise ValueError('Unknown review state')
        if not isinstance(row['refs'], list) or not set(row['refs']) <= set(allowed_refs):
            raise ValueError('Unknown evidence reference')
        for key in ('reason', 'uncertainty'):
            if not isinstance(row[key], str): raise ValueError('Text field required')
        score = row['raw_score']
        if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError('Invalid raw score')
        if row['finding'] == 'UNASSESSED' and score is not None:
            raise ValueError('Missing assessment cannot carry a numeric score')
        if role == 'allow' and row['issue_type'] is not None:
            raise ValueError('Allow does not invent a Deny issue')
        if role == 'deny':
            if row['finding'] == 'ISSUE_FOUND' and row['issue_type'] not in ISSUES:
                raise ValueError('Concrete issue type required')
            if row['finding'] != 'ISSUE_FOUND' and row['issue_type'] is not None:
                raise ValueError('Issue type without a finding')
        if row['finding'] in {'SUPPORTED', 'ISSUE_FOUND'} and not row['refs']:
            raise ValueError('Evidence references required')
    return rows


def qualitative_routes(cards, allow, deny, required_preference_ids=()):
    # Validate completeness before routing; a missing row never becomes no-risk.
    for rows in (allow, deny): validate_complete_assessment(cards, rows)
    aa = {r['use_id']: r for r in allow}; dd = {r['use_id']: r for r in deny}
    result = []
    for card in cards:
        a, d = aa[card['use_id']]['finding'], dd[card['use_id']]['finding']
        if a not in FINDINGS['allow'] or d not in FINDINGS['deny']:
            raise ValueError('Unknown semantic finding')
        action = 'REVIEW'
        if a == 'SUPPORTED' and d == 'NO_ISSUE_FOUND': action = 'KEEP'
        elif a == 'NO_VALUE' and d == 'ISSUE_FOUND': action = 'OMIT'
        elif a == 'NO_VALUE' and d == 'NO_ISSUE_FOUND' and card['preference_id'] not in required_preference_ids:
            action = 'OMIT'
        result.append({'use_id': card['use_id'], 'action': action,
                       'basis': 'predicted_findings_not_verified_safety'})
    return result
