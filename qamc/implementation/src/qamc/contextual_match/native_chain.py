"""Independent dynamic stages, using one durable journal and pacing boundary.

This is execution plumbing for a later frozen release, not a new selector or a
native performance claim. Body-only historical caches are never consulted.
Static query-blind views may be locked separately; query-conditioned stages
must bind to the successful upstream draw from the same root and replicate.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import sqlite3

from qamc.common import sha, canonical, token_estimate
from qamc.bace.runtime import runner_lock
from proposals.qamc_protocol_alignment.sampling import sampling_key, validate_public_request
from proposals.qamc_protocol_alignment.transport import NativeSampler
from proposals.qamc_sentence_units.runtime import frozen, read
from .native_judging import audit_receipts


def checked_plan(protocol, nodes):
    """Freeze a finite DAG of actual draw identities before knowing answers."""
    if (type(protocol.get('concurrency')) is not int or not 1 <= protocol['concurrency'] <= 8
            or protocol.get('spacing_seconds', 0) < 3.1 or not nodes):
        raise ValueError('Bounded concurrency, spacing and nonempty allocation required')
    seen = set(); earlier = {}
    for node in nodes:
        if set(node) != {'unit', 'upstream'} or not isinstance(node['upstream'], list):
            raise ValueError('Explicit node and upstream identities required')
        unit = node['unit']; key = sampling_key(unit)
        if unit['protocol_sha256'] != sha(protocol) or unit['stage'] not in protocol['stages'] or key in seen:
            raise ValueError('Changed protocol, unknown stage or duplicate node')
        if len(set(node['upstream'])) != len(node['upstream']) or not set(node['upstream']) <= seen:
            raise ValueError('Upstreams must be unique earlier nodes of an acyclic allocation')
        for parent in node['upstream']:
            if any(earlier[parent][f] != unit[f] for f in ('root_id', 'replicate')):
                raise ValueError('Query-conditioned input cannot cross root or replicate')
        seen.add(key)
        earlier[key] = unit
    return {'protocol': deepcopy(protocol), 'nodes': deepcopy(nodes), 'maximum_draws': len(nodes),
            'historical_body_cache': False, 'cross_replicate_body_cache': False,
            'native_provider_parity_proven': False}


class Chain:
    """Call under the enclosing phase and parent locks; retain every attempt."""
    def __init__(self, folder, plan, check_release, *, sampler_class=NativeSampler):
        # No folder, client or credentials before the caller's final-release gate.
        check_release(plan)
        if checked_plan(plan['protocol'], plan['nodes']) != plan:
            raise ValueError('Changed dynamic allocation')
        self.folder, self.plan = Path(folder), deepcopy(plan)
        self.check_release, self.sampler_class = check_release, sampler_class
        self.nodes = {sampling_key(n['unit']): n for n in plan['nodes']}
        frozen(self.folder / 'CHAIN_PLAN.json', plan)
        journal = self.folder / 'execution/samples.sqlite'
        if journal.exists():
            with sqlite3.connect(f'file:{journal}?mode=ro', uri=True) as db:
                occupied = {r[0] for r in db.execute('SELECT unit_key FROM samples')}
            if not occupied <= self.nodes.keys():
                raise ValueError('Journal exceeds the frozen chain allocation')

    def output(self, key):
        if key not in self.nodes:
            raise ValueError('Unknown chain node')
        path = self.folder / 'outputs' / (key + '.json')
        return read(path) if path.exists() else None

    def upstream(self, key):
        values = {}
        for parent in self.nodes[key]['upstream']:
            saved = self.output(parent)
            if saved is None or saved['status'] != 'OK':
                raise ValueError('Upstream draw unavailable; do not fabricate a downstream input')
            self.audit(parent)
            values[parent] = saved
        return values

    def audit(self, key):
        """A logical OK needs its own original request/record/response triplet."""
        path = self.folder / 'inputs' / (key + '.json')
        saved_input = read(path)
        job = {'unit': self.nodes[key]['unit'], 'request': saved_input['request']}
        output = self.output(key)
        receipt_folder = self.folder / 'execution/visible' / key
        receipts = {}
        if (receipt_folder / 'record.json').exists():
            receipts[key] = {name: read(receipt_folder / (name + '.json'))
                             for name in ('request', 'record', 'response')}
        manifest = {'protocol': self.plan['protocol'], 'units': [job],
                    'maximum_physical_dispatches': 1, 'cross_replicate_body_cache': False,
                    'historical_body_cache': False}
        return audit_receipts(manifest, {key: output} if output else {}, receipts)[key]

    def execute(self, batch_name, jobs):
        """Freeze late-built requests, then draw each eligible node at most once.

        Existing outputs/journal claims are unit-key reuse, never fresh draws.
        The same physical execution directory preserves pacing and cooldown
        across Task, Selector and Actor, including stage transitions.
        """
        self.check_release(self.plan)
        if not batch_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in batch_name):
            raise ValueError('Explicit safe immutable batch name required')
        jobs = deepcopy(jobs); seen = set()
        for job in jobs:
            if set(job) != {'unit', 'request'}:
                raise ValueError('Public job fields only')
            key = sampling_key(job['unit'])
            if key in seen or key not in self.nodes or job['unit'] != self.nodes[key]['unit']:
                raise ValueError('Duplicate or unallocated dynamic draw')
            seen.add(key); validate_public_request(job['request'])
            config = self.plan['protocol']['stages'][job['unit']['stage']]
            if any(job['request'][f] != value for f, value in
                   [('model', self.plan['protocol']['model']), ('temperature', config['temperature']),
                    ('max_tokens', config['max_tokens'])]):
                raise ValueError('Dynamic request differs from frozen stage settings')
            parents = self.upstream(key)
            frozen(self.folder / 'inputs' / (key + '.json'),
                   {'request': job['request'], 'upstream_outputs': {p: sha(v) for p, v in parents.items()}})
        frozen(self.folder / 'batches' / (batch_name + '.json'), {'jobs': jobs})
        if not jobs:
            return []
        manifest = {'protocol': self.plan['protocol'], 'units': jobs}
        with runner_lock(self.folder / 'stage.lock'):
            # Oversize input is an offline availability failure for that node,
            # never truncation, a model semantic error, or a whole-batch abort.
            for job in jobs:
                key = sampling_key(job['unit'])
                text = canonical(job['request']['messages'])
                if self.output(key) is None and (len(text.encode()) > 2_000_000 or token_estimate(text) > 32768):
                    frozen(self.folder / 'outputs' / (key + '.json'), {
                        'unit': job['unit'], 'request_sha256': sha(job['request']),
                        'status': 'FAILED_OR_RETAINED', 'error_type': 'OFFLINE_INPUT_CAPACITY',
                        'new_physical_request': False, 'score': None})
            pending = [j for j in jobs if self.output(sampling_key(j['unit'])) is None]
            if not pending:
                results = []
                for job in jobs:
                    key = sampling_key(job['unit']); saved = self.output(key)
                    if saved['unit'] != job['unit'] or saved['request_sha256'] != sha(job['request']):
                        raise ValueError('Saved dynamic input changed')
                    self.audit(key); results.append(saved)
                return results
            manifest['units'] = pending
            sampler = self.sampler_class(self.folder / 'execution', manifest)
            try:
                def one(job):
                    key = sampling_key(job['unit']); path = self.folder / 'outputs' / (key + '.json')
                    saved = self.output(key)
                    if saved is not None:
                        if saved['unit'] != job['unit'] or saved['request_sha256'] != sha(job['request']):
                            raise ValueError('Saved dynamic input changed')
                        self.audit(key)
                        return saved
                    try:
                        sampled = sampler.perform(job['unit'], job['request'])
                        result = {'unit': job['unit'], 'request_sha256': sha(job['request']),
                                  'status': 'OK', **sampled}
                    except Exception as error:
                        result = {'unit': job['unit'], 'request_sha256': sha(job['request']),
                                  'status': 'FAILED_OR_RETAINED', 'error_type': type(error).__name__, 'score': None}
                    frozen(path, result)
                    if result['status'] == 'OK':
                        self.audit(key)
                    return result
                with ThreadPoolExecutor(max_workers=self.plan['protocol']['concurrency']) as pool:
                    return list(pool.map(one, jobs))
            finally:
                sampler.close()
