"""Independent native draws using the existing durable sampling transport.

Unlike the development Runtime, this boundary never searches a body-only cache.
Inputs for each replicate must already exist; it does not clone one selected
view and pretend the upstream stages ran independently. Dataset metadata only
controls allocation and never enters a model request here.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import sqlite3

from qamc.common import sha
from qamc.bace.runtime import runner_lock
from proposals.qamc_protocol_alignment.sampling import sampling_key, validate_public_request
from proposals.qamc_protocol_alignment.transport import NativeSampler
from proposals.qamc_sentence_units.runtime import frozen, read


def build_manifest(cases, requests, method_order, protocol, stage):
    """Freeze exact requests by root/method/replicate, not by body alone.

    cases contains only uid and category. requests[uid][method][replicate]
    holds an already constructed public request. Repetition counts belong to
    protocol.repeat_policy; the caller freezes author-version choices first.
    Equal methods may share the same draw *within one root and replicate*.
    """
    cases, requests, protocol = deepcopy(cases), deepcopy(requests), deepcopy(protocol)
    if not cases or not method_order or len(set(method_order)) != len(method_order):
        raise ValueError('Nonempty frozen roots and unique method priority required')
    if any(not isinstance(m, str) or not m for m in method_order):
        raise ValueError('Explicit method names required')
    policy = protocol.get('repeat_policy')
    if (not isinstance(policy, dict) or not policy
            or any(type(n) is not int or not 1 <= n <= 3 for n in policy.values())
            or stage not in protocol['stages']):
        raise ValueError('Explicit bounded repetition policy and stage required')
    if any(set(c) != {'uid', 'category'} or not isinstance(c['uid'], str) or not c['uid']
           or c['category'] not in policy for c in cases):
        raise ValueError('Allocation metadata must identify only root and known category')
    ids = [c['uid'] for c in cases]
    if len(set(ids)) != len(ids) or set(requests) != set(ids):
        raise ValueError('Duplicate roots or changed request coverage')
    units, assignments = [], []
    settings = protocol['stages'][stage]
    for case in cases:
        uid, count = case['uid'], policy[case['category']]
        if set(requests[uid]) != set(method_order):
            raise ValueError('All frozen methods need explicit per-replicate inputs')
        if any(set(requests[uid][m]) != set(range(count)) for m in method_order):
            raise ValueError('Every independent replicate needs its own stage input')
        for replicate in range(count):
            groups = {}
            for method in method_order:
                body = requests[uid][method][replicate]
                validate_public_request(body)
                if (body['model'] != protocol['model'] or body['temperature'] != settings['temperature']
                        or body['max_tokens'] != settings['max_tokens'] or body.get('stream') is not True
                        or body.get('stream_options') != {'include_usage': True}):
                    raise ValueError('Request differs from frozen model/stage configuration')
                group = groups.setdefault(sha(body), {'request': body, 'methods': []})
                group['methods'].append(method)
            for group in groups.values():
                owner = group['methods'][0]  # Declared priority, never answer/score selection.
                unit = {'protocol_sha256': sha(protocol), 'root_id': uid, 'method': owner,
                        'replicate': replicate, 'stage': stage}
                units.append({'unit': unit, 'request': group['request']})
                for method in group['methods']:
                    assignments.append({'root_id': uid, 'category': case['category'],
                        'method': method, 'replicate': replicate, 'stage': stage,
                        'sample_key': sampling_key(unit), 'owner_method': owner,
                        'request_sha256': sha(group['request']),
                        'shared_across_methods': len(group['methods']) > 1})
    return {'protocol': protocol, 'units': units, 'assignments': assignments,
            'root_count': len(cases), 'maximum_physical_dispatches': len(units),
            'cross_replicate_body_cache': False, 'historical_body_cache': False,
            'native_judge_provider_parity_proven': False}


def execute_manifest(folder, manifest, check_release, *, sampler_class=NativeSampler):
    """Execute a caller-approved finite stage with unit-only restart reuse.

    check_release must enforce the final release/partition/parent gate before
    any sampler construction. This function does not choose a method, split,
    author protocol, judge or model. No historical cache argument is accepted.
    """
    manifest = deepcopy(manifest)
    check_release(manifest)
    folder = Path(folder)
    if (manifest.get('cross_replicate_body_cache') is not False
            or manifest.get('historical_body_cache') is not False
            or manifest['maximum_physical_dispatches'] != len(manifest['units'])):
        raise ValueError('Independent sampling boundary changed')
    allowed = {sampling_key(j['unit']) for j in manifest['units']}
    if len(allowed) != len(manifest['units']):
        raise ValueError('Duplicate sampling identities')
    with runner_lock(folder/'runner.lock'):
        check_release(manifest)
        frozen(folder/'MANIFEST.json', manifest)
        journal = folder/'execution/samples.sqlite'
        if journal.exists():
            with sqlite3.connect(f'file:{journal}?mode=ro', uri=True) as db:
                occupied = {r[0] for r in db.execute('SELECT unit_key FROM samples')}
            if not occupied <= allowed:
                raise ValueError('Existing journal exceeds this immutable allocation')
        prior_receipts = {p.parent.name for p in (folder/'execution/visible').glob('*/record.json')}
        sampler = sampler_class(folder/'execution', manifest)
        try:
            def one(job):
                unit, body = job['unit'], job['request']
                path = folder/'outputs'/(sampling_key(unit)+'.json')
                if path.exists():
                    previous = read(path)
                    if previous['unit'] != unit or previous['request_sha256'] != sha(body):
                        raise ValueError('Saved sampling unit input changed')
                    return previous
                try:
                    sampled = sampler.perform(unit, body)
                    result = {'unit': unit, 'request_sha256': sha(body), 'status': 'OK', **sampled}
                except Exception as error:
                    # The transport preserves sanitized physical details. A
                    # crashed/failed journal claim must never become a resend.
                    result = {'unit': unit, 'request_sha256': sha(body), 'status': 'FAILED_OR_RETAINED',
                              'error_type': type(error).__name__, 'score': None}
                frozen(path, result)
                return result
            with ThreadPoolExecutor(max_workers=manifest['protocol']['concurrency']) as pool:
                results = list(pool.map(one, manifest['units']))
        finally:
            sampler.close()
        new_receipts = {p.parent.name for p in (folder/'execution/visible').glob('*/record.json')} - prior_receipts
    return {'results': results, 'assignments': deepcopy(manifest['assignments']),
            'new_physical_requests_this_execution': len(new_receipts),
            'native_judge_provider_parity_proven': False}
