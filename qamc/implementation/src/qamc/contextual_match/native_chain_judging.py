"""Bind sparse dynamic-generation draws to evaluation-only Persist Judges.

The generation artifact has all planned Actor slots, including unavailable
upstream/Actor draws. No empty evidence or placeholder answer is manufactured
to force a complete Actor manifest. Scores never enter the generation chain.
"""
from copy import deepcopy
import sqlite3

from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key, validate_public_request
from proposals.qamc_protocol_alignment.transport import DispatchControl
from proposals.qamc_sentence_units.runtime import read
from .metrics import persist_failure_table
from .native_generation import generation_plan
from .native_judging import REPEATS, audit_receipts
from .native_repeats import execute_manifest


def execute_judges(chain, folder, manifest, check_release, **execution_options):
    """Carry the last generation cooldown into the separate evaluation runtime.

    A stream failure in the last Actor must not lose its remaining five-minute
    wait merely because the Judge has a different journal/model namespace.
    Quota/auth stops remain pre-dispatch stops, not failed scoring attempts.
    """
    from pathlib import Path
    folder = Path(folder)
    def gate(value):
        check_release(value)
        source = chain.folder / 'execution/dispatch.sqlite'
        if not source.exists():
            return
        with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as db:
            next_at, cooldown, hard_stop = db.execute(
                'SELECT next_at,cooldown_until,hard_stop FROM dispatch WHERE id=1').fetchone()
        if hard_stop:
            raise RuntimeError('Generation quota/auth stop retained; no Judge dispatch')
        target = folder / 'execution/dispatch.sqlite'
        if target.exists():
            with sqlite3.connect(f'file:{target}?mode=ro', uri=True) as db:
                if db.execute('SELECT hard_stop FROM dispatch WHERE id=1').fetchone()[0]:
                    raise RuntimeError('Evaluation quota/auth stop retained; no Judge dispatch')
        target.parent.mkdir(parents=True, exist_ok=True)
        control = DispatchControl(target, value['protocol']['spacing_seconds'])
        try:
            control.db.execute('UPDATE dispatch SET next_at=MAX(next_at,?), '
                               'cooldown_until=MAX(cooldown_until,?) WHERE id=1', (next_at, cooldown))
            control.db.commit()
        finally:
            control.close()
    return execute_manifest(folder, manifest, gate, **execution_options)


def build_judges(chain, cases, methods, protocol, judge_request):
    if generation_plan([{k: c[k] for k in ('uid', 'category')} for c in cases], methods,
                       chain.plan['protocol']) != chain.plan or protocol['repeat_policy'] != REPEATS:
        raise ValueError('Actor allocation or Judge repeat policy changed')
    if any(set(c) != {'uid', 'category', 'group_id'} or not c['group_id'] for c in cases):
        raise ValueError('Declared evaluation grouping required')
    saved = read(chain.folder / 'GENERATION_RESULT.json')
    if saved['case_allocation'] != [{k: c[k] for k in ('uid', 'category')} for c in cases]:
        raise ValueError('Evaluation category/row order differs from the frozen generation allocation')
    expected = {sampling_key(n['unit']): n['unit'] for n in chain.plan['nodes'] if n['unit']['stage'] == 'Actor'}
    rows = saved['rows']
    if len(rows) != len(expected) or {r['actor_sample_key'] for r in rows} != expected.keys():
        raise ValueError('Incomplete or duplicate planned Actor slots')
    index = {}
    for row in rows:
        key = row['actor_sample_key']; unit = expected[key]
        if any(row[field] != unit[name] for field, name in
               [('uid', 'root_id'), ('method', 'method'), ('replicate', 'replicate')]):
            raise ValueError('Actor row belongs to another root, method or replicate')
        index[(row['uid'], row['method'], row['replicate'])] = row
    jobs, links, skipped = [], [], []
    for case in cases:
        for rep in range(REPEATS[case['category']]):
            groups = {}
            for method in methods:
                row = index[(case['uid'], method, rep)]; key = row['actor_sample_key']
                link = {'root_id': case['uid'], 'category': case['category'], 'method': method,
                        'replicate': rep, 'actor_sample_key': key}
                if row['status'] == 'UPSTREAM_UNAVAILABLE':
                    if chain.output(key) is not None:
                        raise ValueError('An unavailable upstream slot unexpectedly has an Actor output')
                    skipped.append({**link, 'reason': 'UPSTREAM_UNAVAILABLE'})
                    continue
                audited = chain.audit(key)
                if not audited['available']:
                    if row['status'] != 'ACTOR_UNAVAILABLE':
                        raise ValueError('Actor availability differs from real receipt')
                    skipped.append({**link, 'reason': 'ACTOR_UNAVAILABLE'})
                    continue
                if row['status'] != 'ANSWER_AVAILABLE' or row['actor_request_sha256'] != audited['request_sha256']:
                    raise ValueError('Saved generation availability or wire hash differs from real receipt')
                body = judge_request(case['uid'], case['category'], audited['answer'])
                validate_public_request(body)
                config = protocol['stages']['PersistJudge']
                if (body['model'] != protocol['model'] or body['temperature'] != config['temperature']
                        or body['max_tokens'] != config['max_tokens'] or body.get('stream') is not True
                        or body.get('stream_options') != {'include_usage': True}):
                    raise ValueError('Judge differs from frozen evaluation protocol')
                groups.setdefault(sha(body), {'request': deepcopy(body), 'links': []})['links'].append(
                    {**link, 'actor_answer_sha256': sha(audited['answer'])})
            for group in groups.values():
                unit = {'protocol_sha256': sha(protocol), 'root_id': case['uid'],
                        'method': group['links'][0]['method'], 'replicate': rep, 'stage': 'PersistJudge'}
                key = sampling_key(unit)
                jobs.append({'unit': unit, 'request': group['request']})
                links.extend({**link, 'sample_key': key, 'request_sha256': sha(group['request'])}
                             for link in group['links'])
    return {'protocol': deepcopy(protocol), 'units': jobs, 'assignments': links,
            'skipped_upstream_draws': skipped, 'maximum_physical_dispatches': len(jobs),
            'root_count': len(cases), 'cross_replicate_body_cache': False, 'historical_body_cache': False,
            'planned_actor_draws': len(expected), 'generation_result_sha256': sha(saved),
            'chain_plan_sha256': sha(chain.plan), 'native_judge_provider_parity_proven': False}


def report(chain, cases, methods, manifest, outputs, receipts, judge_request, decode):
    if build_judges(chain, cases, methods, manifest['protocol'], judge_request) != manifest:
        raise ValueError('Judge manifest differs from actual dynamic Actor answers')
    audited = audit_receipts(manifest, outputs, receipts)
    links = {(r['root_id'], r['method'], r['replicate']): r for r in manifest['assignments']}
    skips = {(r['root_id'], r['method'], r['replicate']): r for r in manifest['skipped_upstream_draws']}
    by_method = {}
    for method in methods:
        rows = []
        for case in cases:
            scores, traces = [], []
            for rep in range(REPEATS[case['category']]):
                slot = case['uid'], method, rep; link = links.get(slot); rating = None; error = None
                status = skips[slot]['reason'] if link is None else 'JUDGE_UNAVAILABLE'
                if link is not None and audited[link['sample_key']]['available']:
                    try:
                        rating = decode(case['category'], audited[link['sample_key']]['answer'])['rating']
                        maximum = 3 if case['category'] == 'beneficial_memory_usage' else 5
                        if type(rating) is not int or not 1 <= rating <= maximum:
                            raise ValueError('Invalid structured rating')
                        status = 'SCORED'
                    except (ValueError, KeyError, TypeError) as exc:
                        error = type(exc).__name__; status = 'JUDGE_CONTRACT_ERROR'; rating = None
                scores.append(rating)
                trace = link if link is not None else skips[slot]
                traces.append({'replicate': rep, 'status': status, 'score_error_type': error,
                               'actor_sample_key': trace['actor_sample_key'],
                               'judge_sample_key': link['sample_key'] if link is not None else None})
            rows.append({**case, 'scores': scores, 'draws': traces})
        by_method[method] = {'rows': rows, 'metrics': persist_failure_table(rows)}
    return {'by_method': by_method, 'chain_plan_sha256': sha(chain.plan),
            'judge_manifest_sha256': sha(manifest), 'native_repeat_structure_checked': True,
            'native_judge_provider_parity_proven': False, 'not_a_native_SOTA_claim': True,
            'new_model_calls': 0}
