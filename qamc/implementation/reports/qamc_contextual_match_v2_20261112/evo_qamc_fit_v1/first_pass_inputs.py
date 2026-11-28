"""Verify development feedback and freeze a source-disjoint first-pass trial."""
from collections import Counter
import json

from joint_context import OUT as FIT_OUT, metrics, prepare as fit, read, sha
from baselines import rpe, transfer
from exposure_controls import assemble

QUOTAS = {
    ('RPEval', 'all_A'): 4,
    ('RPEval', 'B_only'): 4,
    ('RPEval', 'contains_C'): 4,
    ('BenchPreS', 'communication'): 4,
    ('PersistBench', 'cross_domain'): 3,
    ('PersistBench', 'sycophancy'): 3,
    ('PersistBench', 'beneficial_memory_usage'): 3,
}


def fit_feedback(rows, case_index, strong):
    feedback = {}
    for domain, pile in strong.items():
        pool = []
        for uid, row in rows.items():
            if uid not in pile or row['benchmark'] != domain:
                continue
            card = case_index[uid]
            current = metrics(card, row['score'])
            opponent = metrics(card, pile[uid]['base_score'])
            if current is None or opponent is None or current['positions'] != opponent['positions']:
                continue
            if row['answer'] == pile[uid]['base_answer']:
                continue
            if domain == 'RPEval' and (row.get('score_flags') != [] or card['base_flags'] != []):
                continue
            pool.append((card, row, current, opponent, pile[uid]['base_answer']))
        chosen, groups = [], set()
        for objective in ('repair', 'protect', 'contrast'):
            options = []
            for item in pool:
                card, _, a, b, _ = item
                if card['group'] in groups:
                    continue
                gap = b['primary'] - a['primary']
                if (objective == 'repair' and gap <= 0) or (objective == 'protect' and gap >= 0):
                    continue
                options.append(((-abs(gap), sha(card['uid'])), item))
            if not options:
                continue
            _, (card, row, current, opponent, preferred) = min(options)
            groups.add(card['group'])
            chosen.append(dict(purpose=objective, task=card['payload']['task'],
                               history=card['payload']['source_evidence'],
                               parent_answer=row['answer'], comparison_answer=preferred,
                               observed_primary_gap=opponent['primary'] - current['primary'],
                               current=current, reference=opponent))
        if len(chosen) < 2:
            raise ValueError(f'Too few distinct feedback groups in {domain}')
        feedback[domain] = chosen
    return feedback


def prepare_inputs():
    fit_pin, cards, _, _, _, _ = fit()
    fit_index = {c['uid']: c for c in cards}
    outcomes = read(FIT_OUT/'RESULTS.json')['rows']
    fit_rows = {r['uid']: r for r in outcomes if r['method'] == 'JCC'}
    fit_groups = {(c['domain'], c['group']) for c in cards}
    strong = {'RPEval': rpe(), 'BenchPreS': transfer('BenchPreS'),
              'PersistBench': transfer('PersistBench')}
    feedback = fit_feedback(fit_rows, fit_index, strong)
    batches, _, service = assemble()
    eligible = {(b['card']['domain'], b['card']['stratum']): []
                for batch in batches for b in batch}
    for batch in batches:
        for bundle in batch:
            card = bundle['card']
            domain, stratum = card['domain'], card['stratum']
            if (domain, card['group']) in fit_groups:
                raise ValueError('Expansion source overlaps offline feedback panel')
            ref = strong[domain].get(card['uid'])
            if ref is not None and bundle['actors'] and metrics(card, ref['base_score']) is not None:
                eligible[domain, stratum].append(bundle)
    schedule = []
    groups = set()
    for key, target in QUOTAS.items():
        domain, _ = key
        count = 0
        for bundle in sorted(eligible[key], key=lambda b: sha(['shared-first-pass-v1', b['card']['uid']])):
            group = domain, bundle['card']['group']
            if domain != 'BenchPreS' and group in groups:
                continue
            groups.add(group)
            schedule.append(bundle)
            count += 1
            if count == target:
                break
        if count != target:
            raise ValueError(f'Insufficient source-disjoint groups for {key}: {count} of {target}')
    reference = {}
    for bundle in schedule:
        card = bundle['card']
        ref = strong[card['domain']][card['uid']]
        reference[card['uid']] = dict(score=ref['base_score'], flags=ref['base_flags'],
                                      answer_fingerprint=ref['baseline_answer_sha256'])
    offline = dict(examples=feedback)
    return fit_pin, schedule, reference, offline, service


if __name__ == '__main__':
    _, roster, _, feedback, _ = prepare_inputs()
    print(json.dumps({
        'proposal_examples': {domain: len(rows) for domain, rows in feedback['examples'].items()},
        'evaluation_tasks': Counter(b['card']['domain'] for b in roster),
        'evaluation_groups': {domain: len({b['card']['group'] for b in roster if b['card']['domain']==domain})
                              for domain in feedback['examples']},
    }, indent=2))
