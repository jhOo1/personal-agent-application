"""Independent-draw evaluation adapter for the frozen draft-origin methods.

This adds no algorithm candidate and changes no running development phase.
Callers must supply an approved release gate to the existing Chain runtime.
No body cache, Store, scorer, labels or benchmark-specific prompts are used.
"""
from copy import deepcopy

from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key
from proposals.qamc_sentence_units.runtime import frozen
from .native_chain import checked_plan
from . import draft_origin_v2 as method

REPEATS = {'rpeval': 1, 'benchpres': 3, 'cross_domain': 3,
           'sycophancy': 3, 'beneficial_memory_usage': 1}


def unit(protocol, uid, name, stage, replicate):
    return {'protocol_sha256': sha(protocol), 'root_id': uid, 'method': name,
            'stage': stage, 'replicate': replicate}


def generation_plan(cases, methods, protocol):
    """Use categories for draw allocation only, never for prompt selection."""
    if (not isinstance(methods, (list, tuple)) or not methods
            or len(set(methods))!=len(methods) or not set(methods)<=set(method.METHODS)
            or not cases or len({c.get('uid') for c in cases})!=len(cases)
            or protocol.get('repeat_policy')!=REPEATS or set(protocol['stages'])!={'Draft', 'Actor'}):
        raise ValueError('Frozen methods, categories, roots and repeat policy required')
    if any(set(c)!={'uid', 'category'} or c['category'] not in REPEATS
           or not isinstance(c['uid'], str) or not c['uid'] for c in cases):
        raise ValueError('Only declared allocation metadata is allowed')
    for stage in ('Draft', 'Actor'):
        settings = protocol['stages'][stage]
        if settings.get('max_tokens')!=4096 or settings.get('temperature') not in (0, 1):
            raise ValueError('New model block may change temperature, not frozen output caps')
    origins = [o for o in method.DRAFTS if any(method.owner(m)==o for m in methods)]
    nodes = []
    for case in cases:
        for rep in range(REPEATS[case['category']]):
            for origin in origins:
                nodes.append({'unit': unit(protocol, case['uid'], origin, 'Draft', rep), 'upstream': []})
            for name in methods:
                parent = unit(protocol, case['uid'], method.owner(name), 'Draft', rep)
                nodes.append({'unit': unit(protocol, case['uid'], name, 'Actor', rep),
                              'upstream': [sampling_key(parent)]})
    return checked_plan(protocol, nodes)


def configured(body, protocol, stage):
    # This is a separately frozen evaluation block. The source prompt and
    # original candidate text are unchanged; decoding/model choices are explicit.
    body = deepcopy(body)
    body['temperature'] = protocol['stages'][stage]['temperature']
    body['max_tokens'] = protocol['stages'][stage]['max_tokens']
    return body


def execute_generation(chain, tasks, cases, methods, base_system):
    """Regenerate each upstream draft within its own root and replicate.

    Two review methods may share their declared same-origin draft within a draw.
    Drafts from a previous development result or another replicate never enter
    these final calls. An unavailable draft has no placeholder final request.
    """
    if generation_plan(cases, methods, chain.plan['protocol'])!=chain.plan:
        raise ValueError('Independent draft-origin allocation changed')
    if set(tasks)!={c['uid'] for c in cases} or any(t.uid!=uid for uid, t in tasks.items()):
        raise ValueError('Complete frozen public tasks required')
    protocol = chain.plan['protocol']; drafts = []
    for node in chain.plan['nodes']:
        u = node['unit']
        if u['stage']!='Draft': continue
        body = method.draft_request(tasks[u['root_id']], base_system, u['method'], protocol['model'])
        drafts.append({'unit': u, 'request': configured(body, protocol, 'Draft')})
    chain.execute('drafts', drafts)
    final = []; rows = []
    for node in chain.plan['nodes']:
        u = node['unit']
        if u['stage']!='Actor': continue
        key = sampling_key(u); parent_key = node['upstream'][0]; saved = chain.output(parent_key)
        row = {'uid': u['root_id'], 'method': u['method'], 'replicate': u['replicate'],
               'actor_sample_key': key, 'draft_sample_key': parent_key, 'status': 'UPSTREAM_UNAVAILABLE',
               'score': None}
        if saved and saved['status']=='OK':
            chain.audit(parent_key)
            body = method.final_request(tasks[u['root_id']], base_system, saved['response']['answer'],
                                        u['method'], protocol['model'])
            body = configured(body, protocol, 'Actor')
            final.append({'unit': u, 'request': body})
            row.update(status='ACTOR_UNAVAILABLE', actor_request_sha256=sha(body),
                       draft_output_sha256=sha(saved))
        rows.append(row)
    chain.execute('actors', final)
    for row in rows:
        if row['status']=='UPSTREAM_UNAVAILABLE': continue
        saved = chain.output(row['actor_sample_key'])
        if saved and saved['status']=='OK':
            checked = chain.audit(row['actor_sample_key'])
            if not checked['available'] or checked['request_sha256']!=row['actor_request_sha256']:
                raise ValueError('Independent final output lacks its own physical receipt')
            row.update(status='ANSWER_AVAILABLE', answer=saved['response']['answer'])
    result = {'case_allocation': deepcopy(cases), 'methods': list(methods), 'rows': rows,
              'all_methods_share_same_public_candidates': True,
              'historical_draft_cache_used': False, 'cross_replicate_cache_used': False,
              'shared_same_origin_draft_is_not_an_independent_replicate': True,
              'native_provider_parity_proven': False, 'benchmark_scores_produced': False}
    frozen(chain.folder/'GENERATION_RESULT.json', result)
    return result
