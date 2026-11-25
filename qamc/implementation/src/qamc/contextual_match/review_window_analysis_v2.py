"""Read-only paired analysis of saved-draft review, never a selection policy."""
from itertools import combinations
import json

from qamc.common import sha
from .answer_use_review_v2 import METHODS, REVIEW_METHODS, build
from .evaluation import aggregate, unique_index
from .factorial_analysis_v2 import higher_is_better, interaction

COORDINATES = dict(zip(REVIEW_METHODS, ('F00', 'F01', 'F10', 'F11')))
PAIRS = tuple((left, right) for left, right in combinations(METHODS, 2))


def validate_lineage(rows, drafts, initial_requests, controls, audits):
    """Rebuild the frozen wire and verify cached outcomes without reading gold."""
    index = unique_index(rows)
    jobs = {(j['unit']['root_id'], j['unit']['method']): j for j in initial_requests}
    audit_index = {(a['uid'], a['method']): a for a in audits}
    if len(jobs) != len(initial_requests) or len(audit_index) != len(audits):
        raise ValueError('Duplicate frozen input identity')
    counts = {}
    for (uid, method), row in index.items():
        if method not in METHODS or uid not in drafts:
            raise ValueError('Unknown review result')
        audit = audit_index[uid, method]
        if row.get('input_audit') != audit:
            raise ValueError('Input audit changed')
        mode = audit['mode']
        counts[mode] = counts.get(mode, 0) + 1
        if method in REVIEW_METHODS:
            built = build(drafts[uid]['actor_request'], drafts[uid]['draft_answer'], method)
            if built['mode'] != mode:
                raise ValueError('Review mode changed')
            expected = built['request']
        else:
            expected = controls[uid][method]['row'].get('actor_request')
        job = jobs.get((uid, method))
        if expected is None:
            if job or row.get('actor_request') or row.get('answer') or row.get('score') is not None:
                raise ValueError('Unavailable saved draft acquired an outcome')
            continue
        if job is None or job['request'] != expected or row.get('actor_request') != expected:
            raise ValueError('Review wire changed')
        if row.get('actor_request_sha256') != sha(expected):
            raise ValueError('Review request hash changed')
        if mode == 'ONE_REVIEW_OF_FIXED_ORIGINAL_DRAFT':
            view = json.loads(expected['messages'][1]['content'])
            if view != {'current_input': json.loads(drafts[uid]['actor_request']['messages'][1]['content']),
                        'draft_answer': drafts[uid]['draft_answer']}:
                raise ValueError('Review evidence or shared draft changed')
        else:
            owner = controls[uid][method if method in controls[uid] else 'ORIGINAL']['row']
            for field in ('answer', 'score', 'actor_status'):
                if row.get(field) != owner.get(field):
                    raise ValueError('Saved control or identity outcome changed')
    return {'verified_rows': len(index), 'modes': counts, 'frozen_wires_rebuilt': True,
            'shared_drafts_and_evidence_verified': True, 'cached_outcomes_unchanged': True}


def review_factorial(rows, cases, draws=2000):
    """F01-F00 is use review; F10-F00 is compaction, on common four sets."""
    projected = [{**r, 'method': COORDINATES[r['method']]} for r in rows if r['method'] in COORDINATES]
    return {'design': 'generic/use draft review x ordinary/compact output contract',
            'coordinates': COORDINATES, 'cached_controls_outside_factorial': True,
            'benchmarks': [interaction(projected, cases, b, draws)
                           for b in ('rpeval', 'benchpres', 'persistbench')]}


def review_queue(rows, cases):
    """All score and attribute changes, including offsetting and judge-only changes."""
    index = unique_index(rows)
    by_uid = {c['uid']: c for c in cases}
    changes, missing = [], []
    for c in cases:
        uid = c['uid']
        if not any((uid, m) in index for m in METHODS):
            continue
        absent = [m for m in METHODS if index.get((uid, m), {}).get('score') is None]
        if absent:
            missing.append({'uid': uid, 'unavailable_methods': absent})
        for left, right in PAIRS:
            a, b = index.get((uid, left)), index.get((uid, right))
            if not a or not b or a.get('score') is None or b.get('score') is None:
                continue
            values = [aggregate(c['benchmark'], [r], by_uid) for r in (a, b)]
            metrics = [{'metric': k, 'left': v, 'right': values[1][k],
                        'delta_left_minus_right': v-values[1][k], 'higher_is_better': higher_is_better(k)}
                       for k, v in values[0].items()
                       if v is not None and values[1][k] is not None and v != values[1][k]]
            details = []
            if c['benchmark'] == 'benchpres':
                ad, bd = a['score']['decisions'], b['score']['decisions']
                if [(d['preference'], d['appropriate']) for d in ad] != [(d['preference'], d['appropriate']) for d in bd]:
                    raise ValueError('Attribute identities changed')
                details = [{'attribute_position': i, 'preference': da['preference'],
                            'appropriate': da['appropriate'], 'left_label': da['label'], 'right_label': db['label']}
                           for i, (da, db) in enumerate(zip(ad, bd)) if da['label'] != db['label']]
            elif c['benchmark'] == 'persistbench' and a['score']['rating'] != b['score']['rating']:
                details = [{'left_rating': a['score']['rating'], 'right_rating': b['score']['rating']}]
            if not metrics and not details:
                continue
            same = a.get('answer') == b.get('answer')
            changes.append({'uid': uid, 'benchmark': c['benchmark'],
                            'group_id': c.get('analysis_group_id', c['group_id']),
                            'left': left, 'right': right, 'endpoints': metrics, 'attribute_or_rating_changes': details,
                            'same_answer': same, 'judge_only_on_same_answer': same,
                            'first_semantic_error': 'UNKNOWN_REQUIRES_SOURCE_REVIEW',
                            'left_mode': a['input_audit']['mode'], 'right_mode': b['input_audit']['mode']})
    return {'pairs_with_saved_difference': changes, 'missing': missing, 'all_pairs_checked': PAIRS,
            'human_reviews': 0, 'automatically_adjudicated_cases': 0, 'scores_modified': False}
