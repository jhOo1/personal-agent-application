"""Reuse only exact completed source/answer reviews; no model calls."""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT)]
import run_qamc_rpreasoner_paper as r
from qamc.transport_helpers import atomic_json


def identity(public, reference, outcome):
    if not outcome.get('answer') or not outcome.get('view'):
        return None
    return r.sha([public, reference, outcome['view'], outcome['answer']])


def main():
    plan = r.read(r.OUT / 'PLAN.json'); r.check(plan)
    pool = defaultdict(list)
    def add(public, reference, outcome, path, note, bounds=None):
        key = identity(public, reference, outcome)
        if key:
            pool[key].append({'source_path': str(path.relative_to(ROOT)), 'source_sha256': r.fh(path),
                              'source_method': outcome.get('arm'), 'observations': note,
                              'conditional_ai_bounds': bounds, 'human_reviews': 0})
    # These old audits explicitly covered their listed methods. Exported,
    # unreviewed answers elsewhere do not enter this reuse pool.
    folder = ROOT / 'reports/qamc_gate_scope_purpose'
    path = folder / 'SOURCE_ANSWER_REVIEW.json'
    details = {v['case']['uid']: v for v in r.read(folder / 'CASE_DETAILS.json')}
    for v in r.read(path)['reviews']:
        c = details[v['uid']]
        for out in [c['candidate'], *c['controls'].values()]:
            add(c['public'], c['evaluation_only_reference'], out, path, v['observations'])
    folder = ROOT / 'reports/qamc_scoped_answer'
    path = folder / 'SOURCE_ANSWER_REVIEW_V9.json'
    packets = {v['uid']: v for p in (folder / 'case_review').glob('*.json') for v in [r.read(p)]}
    for v in r.read(path)['reviews']:
        c = packets[v['uid']]
        all_outcomes = c['scoped'] + c['controls'] + c.get('full', [])
        for row in v['rows']:
            out = next((o for o in all_outcomes if o['arm'] == row['arm']), None)
            if out:
                add(c['public_input'], c['evaluation_only_reference'], out, path,
                    '\n'.join(v['observations']), row['ai_match_bounds'])
    path = r.P0 / 'dispute_reviews/rpeval_all_gate_differences_v1.json'
    p0_cases = {v['uid']: v for v in r.read(r.P0 / 'PLAN.json')['cases']}
    for v in r.read(path)['reviews']:
        c = p0_cases[v['uid']]
        reference = r.read(ROOT / c['evaluation_path']); public = v['parent_full_case']['public']
        add(public, reference, v['P0'], path, v['AI_review_note'])
        for out in v['parent_full_case']['outcomes']:
            if out['arm'] == 'G0':
                add(public, reference, out, path, v['AI_review_note'])
    # The CF0 audit records exact reuse per method and fresh candidate reads.
    cf_details = {v['case']['uid']: v for v in r.read(r.CF / 'CASE_DETAILS.json')}
    path = r.CF / 'SOURCE_ANSWER_REVIEW.json'
    for v in r.read(path)['reviews']:
        c = cf_details[v['uid']]
        for arm, info in v['methods'].items():
            out = c['candidate'] if arm == 'CANDIDATE' else c['controls'][arm]
            assert identity(c['public'], c['evaluation_only_reference'], out) == info['identity']
            if info['prior_reviews'] or arm == 'CANDIDATE':
                add(c['public'], c['evaluation_only_reference'], out, path, v['observations'],
                    v.get('fresh_ai_bounds', {}).get(arm))
    path = r.OUT / 'SOURCE_ANSWER_REVIEW_V1.json'
    for v in r.read(path)['reviews']:
        pool[v['source_reference_view_answer_identity']].append({'source_path': str(path.relative_to(ROOT)),
            'source_sha256': r.fh(path), 'source_method': r.ARM, 'observations': v['observations'],
            'conditional_ai_bounds': None, 'human_reviews': 0})
    rows = []
    for entry in r.read(r.OUT / 'REVIEW_QUEUE.json')['rows']:
        c = r.read(ROOT / entry['packet']); methods = {}
        for arm, out in [('CANDIDATE', c['candidate']), *c['controls'].items()]:
            key = identity(c['public_input'], c['evaluation_only_reference'], out)
            methods[arm] = {'identity': key, 'prior_reviews': pool.get(key, []),
                            'status': 'EXACT_PRIOR_REVIEW' if key in pool else 'NEEDS_TARGETED_READ'}
        rows.append({'uid': entry['uid'], 'methods': methods, 'packet_sha256': r.fh(ROOT / entry['packet']),
                     'needs_read': [a for a, v in methods.items() if v['status'] == 'NEEDS_TARGETED_READ']})
    atomic_json(r.OUT / 'PAIRED_REVIEW_PLAN.json', {'rows': rows, 'human_reviews': 0,
                'new_calls': 0, 'reuse_requires_public_reference_view_answer_identity': True})
    print(json.dumps({'roots': len(rows), 'needs': {v['uid']: v['needs_read'] for v in rows if v['needs_read']},
                      'new_calls': 0}))


if __name__ == '__main__':
    main()
