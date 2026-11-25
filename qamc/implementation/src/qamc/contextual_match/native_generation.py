"""Actual Task -> Selector -> Actor composition for independent protocol draws.

Only already frozen public sources, query-blind sidecars and original prompts
are accepted. This module has no evaluator, benchmark loader or model router.
It does not open SELECT/CONFIRM or authenticate an official provider.
"""
from copy import deepcopy

from qamc.common import sha, parse_object
from proposals.qamc_protocol_alignment.sampling import sampling_key
from proposals.qamc_sentence_units.runtime import frozen
from .native_chain import checked_plan
from .native_judging import REPEATS
from .prompts import request
from .development import read_request, actor_request, decode_representation, text_request
from .controls import typed_request
from .core import compile_match

METHODS = ('R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'RAW', 'QUERY_SUMMARY', 'INCREMENTAL_UNIFIED_ADAPT')
BENCHPRES_REPEATS = {'benchpres': 3}


def generation_repeats(protocol):
    """Allocation metadata controls draws, never the inference prompt itself."""
    policy = protocol.get('repeat_policy')
    if not isinstance(policy, dict) or any(type(n) is not int for n in policy.values()):
        raise ValueError('Integer repeat counts required')
    if (protocol.get('repeat_policy') == REPEATS
            and protocol.get('benchmark', 'persistbench') == 'persistbench'):
        return REPEATS
    if (protocol.get('benchmark') == 'benchpres'
            and protocol.get('repeat_policy') == BENCHPRES_REPEATS
            and type(protocol.get('stages', {}).get('Actor', {}).get('temperature')) in (int, float)
            and protocol['stages']['Actor']['temperature'] == 1):
        return BENCHPRES_REPEATS
    raise ValueError('Explicit Persist 3/3/1 or BenchPreS three-answer temperature-1 policy required')


def unit(protocol, uid, method, replicate, stage):
    return {'protocol_sha256': sha(protocol), 'root_id': uid, 'method': method,
            'replicate': replicate, 'stage': stage}


def generation_plan(cases, methods, protocol):
    repeats = generation_repeats(protocol)
    if (not methods
            or len(set(methods)) != len(methods) or set(methods) - set(METHODS)):
        raise ValueError('Explicit known methods required')
    if (not cases or any(set(c) != {'uid', 'category'} or c['category'] not in repeats for c in cases)
            or len({c['uid'] for c in cases}) != len(cases)):
        raise ValueError('Only unique root/category allocation metadata allowed')
    nodes = []
    def add(uid, method, rep, stage, upstream=()):
        value = unit(protocol, uid, method, rep, stage)
        nodes.append({'unit': value, 'upstream': list(upstream)})
        return sampling_key(value)
    for case in cases:
        for rep in range(repeats[case['category']]):
            uid = case['uid']; task_key = None; typed_key = None; readers = {}
            if set(methods) & {'R3', 'R4', 'R5'}:
                task_key = add(uid, 'SHARED_TASK', rep, 'Task')
            if set(methods) & {'R4', 'R5'}:
                typed_key = add(uid, 'R4_R5_SHARED', rep, 'TypedMatcher', [task_key])
            for method in methods:
                if method == 'RAW':
                    readers[method] = None
                elif method in {'R4', 'R5'}:
                    readers[method] = typed_key
                else:
                    stage = 'QuerySummary' if method == 'QUERY_SUMMARY' else 'Selector'
                    readers[method] = add(uid, method, rep, stage, [task_key] if method == 'R3' else [])
            for method in methods:
                add(uid, method, rep, 'Actor', [readers[method]] if readers[method] else [])
    return checked_plan(protocol, nodes)


def execute_generation(chain, tasks, cases, methods, static_views, prompts, *, incremental=None):
    """Run the original inference functions separately for every replicate.

    static_views[uid] contains Memory and/or MemorySummary from a separately
    frozen, source-bound snapshot. No TaskView/Selector/Actor from development
    is accepted. The enclosing release check must bind these static witnesses.
    """
    if generation_plan(cases, methods, chain.plan['protocol']) != chain.plan or set(tasks) != {c['uid'] for c in cases}:
        raise ValueError('Public tasks or independent stage allocation changed')
    if any(task.uid != uid for uid, task in tasks.items()):
        raise ValueError('Public task identity mismatch')
    if set(static_views) - tasks.keys() or any(set(v) - {'Memory', 'MemorySummary'} for v in static_views.values()):
        raise ValueError('Only declared query-blind static views can be reused')
    inc = {uid: incremental(task) for uid, task in tasks.items()} if 'INCREMENTAL_UNIFIED_ADAPT' in methods and incremental else {}
    if 'INCREMENTAL_UNIFIED_ADAPT' in methods and len(inc) != len(tasks):
        raise ValueError('Frozen Incremental public request builder required')
    frozen(chain.folder / 'STATIC_INPUTS.json', {
        'public_inputs': {uid: sha(task.payload()) for uid, task in tasks.items()},
        'static_views': deepcopy(static_views), 'prompts': deepcopy(prompts),
        'incremental_wire_sha256': {uid: sha(body) for uid, body in inc.items()}})
    protocol = chain.plan['protocol']; task_views = {}; failures = {}; actors = []; rows = []
    def wire(body, stage):
        # Model and sampling are explicit release settings, not a quiet fallback.
        return {**body, 'model': protocol['model'], **protocol['stages'][stage]}
    def job(node, body):
        return {'unit': node['unit'], 'request': wire(body, node['unit']['stage'])}
    def answer(key):
        saved = chain.output(key)
        if saved is None or saved['status'] != 'OK':
            raise ValueError('Upstream transport unavailable')
        chain.audit(key)
        return saved['response']['answer']
    def record_failure(key, error):
        # Structural/transport unavailability is not a semantic model mistake.
        failures[key] = {'error_type': type(error).__name__, 'status': 'UPSTREAM_OR_CONTRACT_UNAVAILABLE'}
    nodes = chain.plan['nodes']
    task_jobs = [job(n, request('Task', tasks[n['unit']['root_id']], protocol['model'],
                              protocol['stages']['Task']['max_tokens']))
                 for n in nodes if n['unit']['stage'] == 'Task']
    chain.execute('task', task_jobs)
    for n in nodes:
        if n['unit']['stage'] != 'Task':
            continue
        key = sampling_key(n['unit'])
        try:
            task_views[key] = decode_representation(tasks[n['unit']['root_id']], 'Task', answer(key))['view']
        except (ValueError, KeyError, TypeError) as error:
            record_failure(key, error)
    readers = []
    for n in nodes:
        u = n['unit']; key = sampling_key(u); stage = u['stage']
        if stage in {'Task', 'Actor'}:
            continue
        task = tasks[u['root_id']]; sidecar = static_views.get(task.uid, {})
        try:
            if n['upstream'] and any(p not in task_views for p in n['upstream']):
                raise ValueError('This replicate lacks a valid TaskView')
            task_view = task_views[n['upstream'][0]] if n['upstream'] else None
            if stage == 'TypedMatcher':
                body = typed_request(task, sidecar.get('Memory'), task_view, prompts['style_selector'])
            else:
                method = u['method']
                memory = sidecar.get('MemorySummary' if method == 'R1' else 'Memory') if method in {'R1', 'R2', 'R3'} else None
                body = read_request(task, method, prompts, memory, task_view, inc.get(task.uid))
            readers.append(job(n, body))
        except (ValueError, KeyError, TypeError) as error:
            record_failure(key, error)
    chain.execute('readers', readers)
    for n in nodes:
        u = n['unit']
        if u['stage'] != 'Actor':
            continue
        key = sampling_key(u); task = tasks[u['root_id']]
        row = {'uid': task.uid, 'method': u['method'], 'replicate': u['replicate'],
               'actor_sample_key': key, 'status': 'UPSTREAM_UNAVAILABLE',
               'upstream_sample_keys': list(n['upstream'])}
        rows.append(row)
        try:
            prior = answer(n['upstream'][0]) if n['upstream'] else None
            if u['method'] in {'R4', 'R5'}:
                # Compile only this arm, as in the frozen development runner.
                # A rejected R5 support target must not discard valid R4 seeds.
                built = compile_match(task, parse_object(prior), closure=u['method'] == 'R5')
                built['request'] = text_request(prompts['actor'], built['view'], cap=4096)
            else:
                built = actor_request(task, u['method'], prior, prompts)
            j = job(n, built['request']); actors.append(j)
            row.update(status='ACTOR_READY', actor_request_sha256=sha(j['request']),
                       evidence_view_sha256=sha(built['view']))
        except (ValueError, KeyError, TypeError) as error:
            record_failure(key, error)
    chain.execute('actors', actors)
    for row in rows:
        if row['status'] != 'ACTOR_READY':
            continue
        saved = chain.output(row['actor_sample_key'])
        row['status'] = 'ANSWER_AVAILABLE' if saved and saved['status'] == 'OK' else 'ACTOR_UNAVAILABLE'
    result = {'rows': rows, 'case_allocation': deepcopy(cases), 'failures': failures, 'planned_actor_draws': len(rows),
              'actual_actor_jobs': actors, 'query_blind_static_views_reused': True,
              'query_conditioned_stages_repeated': True, 'scores': None,
              'native_provider_parity_proven': False, 'not_a_native_SOTA_claim': True}
    frozen(chain.folder / 'GENERATION_RESULT.json', result)
    return result
