"""Receipt-bound scoring for independent draft-origin generation chains.

Scorers are supplied by a frozen release; this module does not choose a model,
rubric, sample, method or split. No labels enter the generation chain. It never
creates placeholder Actor inputs to obtain a nominally complete scoring table.
"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key, validate_public_request
from proposals.qamc_sentence_units.runtime import read, frozen
from .native_draft_origin_v2 import generation_plan, REPEATS
from .native_chain_judging import execute_judges
from .native_judging import audit_receipts
from .metrics import persist_failure_table

PERSIST = {'cross_domain', 'sycophancy', 'beneficial_memory_usage'}


def stages(category):
    if category in PERSIST: return ('PersistJudge',)
    if category=='rpeval': return ('RPEvalJudge',)
    if category=='benchpres': return (*(f'BenchAttr{i}' for i in range(5)), 'BenchComplete')
    raise ValueError('Unknown evaluation-only category')


def build_judges(chain, cases, methods, protocols, judge_specs):
    if any(set(c)!={'uid', 'category', 'group_id'} or not c['group_id'] for c in cases):
        raise ValueError('Explicit evaluation allocation and source groups required')
    allocation = [{k: c[k] for k in ('uid', 'category')} for c in cases]
    if generation_plan(allocation, methods, chain.plan['protocol'])!=chain.plan:
        raise ValueError('Generation allocation changed')
    saved = read(chain.folder/'GENERATION_RESULT.json')
    if saved['case_allocation']!=allocation or saved['methods']!=list(methods):
        raise ValueError('Evaluation category, order or methods changed after generation')
    expected = {sampling_key(n['unit']): n for n in chain.plan['nodes'] if n['unit']['stage']=='Actor'}
    rows = saved['rows']
    if len(rows)!=len(expected) or {r['actor_sample_key'] for r in rows}!=set(expected):
        raise ValueError('Missing or duplicate planned Actor rows')
    index = {}
    for row in rows:
        node = expected[row['actor_sample_key']]; u = node['unit']
        if any(row[a]!=u[b] for a, b in [('uid', 'root_id'), ('method', 'method'), ('replicate', 'replicate')]):
            raise ValueError('Actor row belongs to a different draw')
        index[row['uid'], row['method'], row['replicate']] = row
    manifests = {}; links = []; skipped = []
    for case in cases:
        protocol = protocols[case['category']]; pid = sha(protocol)
        if protocol.get('repeat_policy')!=REPEATS:
            raise ValueError('Scorer repeat policy differs')
        block = manifests.setdefault(pid, {'protocol': deepcopy(protocol), 'units': [],
            'maximum_physical_dispatches': 0, 'historical_body_cache': False,
            'cross_replicate_body_cache': False, 'native_judge_provider_parity_proven': False})
        for rep in range(REPEATS[case['category']]):
            groups = {}
            for name in methods:
                row = index[case['uid'], name, rep]; key = row['actor_sample_key']
                link = {'root_id': case['uid'], 'category': case['category'], 'method': name,
                        'replicate': rep, 'actor_sample_key': key}
                node = expected[key]
                if row['draft_sample_key']!=node['upstream'][0]:
                    raise ValueError('Final row references the wrong draft')
                if row['status']=='UPSTREAM_UNAVAILABLE':
                    draft = chain.output(node['upstream'][0])
                    if chain.output(key) is not None or (draft is not None and draft['status']=='OK'):
                        raise ValueError('Unavailable upstream row contradicts saved generation')
                    skipped.append({**link, 'reason': 'UPSTREAM_UNAVAILABLE'}); continue
                actor = chain.audit(key)
                if not actor['available']:
                    if row['status']!='ACTOR_UNAVAILABLE': raise ValueError('Actor failure status changed')
                    skipped.append({**link, 'reason': 'ACTOR_UNAVAILABLE'}); continue
                if (row['status']!='ANSWER_AVAILABLE' or row['actor_request_sha256']!=actor['request_sha256']
                        or row['answer']!=actor['answer']):
                    raise ValueError('Final answer differs from its real physical receipt')
                if case['category']=='rpeval':
                    body = read(chain.folder/'inputs'/(key+'.json'))['request']
                    view = json.loads(body['messages'][1]['content'])['current_input']
                    count = len(view['candidate_memory'])
                    if count<1: raise ValueError('RPEval public candidate count is unavailable')
                    link['expected_metric_items'] = count
                specs = judge_specs(case['uid'], case['category'], actor['answer'])
                wanted = stages(case['category'])
                if len(specs)!=len(wanted) or {s['stage'] for s in specs}!=set(wanted):
                    raise ValueError('Missing, duplicate or extra native scorer stage')
                for spec in specs:
                    if set(spec)!={'stage', 'request'}: raise ValueError('Public scorer job fields only')
                    stage, body = spec['stage'], spec['request']; validate_public_request(body)
                    config = protocol['stages'][stage]
                    if (body['model']!=protocol['model'] or body['temperature']!=config['temperature']
                            or body['max_tokens']!=config['max_tokens']):
                        raise ValueError('Scorer request differs from frozen protocol')
                    groups.setdefault((stage, sha(body)), {'request': deepcopy(body), 'links': [],
                        'stage': stage})['links'].append({**link, 'actor_answer_sha256': sha(actor['answer'])})
            # Exact scoring reuse is within root, replicate and metric stage.
            # An identical answer in another replicate remains a new draw.
            for group in groups.values():
                u = {'protocol_sha256': pid, 'root_id': case['uid'], 'method': group['links'][0]['method'],
                     'replicate': rep, 'stage': group['stage']}
                key = sampling_key(u); block['units'].append({'unit': u, 'request': group['request']})
                links.extend({**v, 'stage': group['stage'], 'protocol_id': pid, 'sample_key': key,
                              'request_sha256': sha(group['request'])} for v in group['links'])
    for pid, block in manifests.items():
        block['maximum_physical_dispatches'] = len(block['units'])
        block['assignments'] = [link for link in links if link['protocol_id']==pid]
    return {'manifests': manifests, 'assignments': links, 'skipped_actor_draws': skipped,
            'case_allocation': deepcopy(cases), 'methods': list(methods),
            'planned_actor_draws': len(expected), 'generation_result_sha256': sha(saved),
            'chain_plan_sha256': sha(chain.plan), 'native_provider_parity_proven': False}


def execute_bundle(chain, folder, bundle, check_release, *, sampler_classes=None):
    """Run frozen scorer blocks sequentially with shared predecessor cooldown."""
    check_release(bundle); folder = Path(folder)
    for pid, manifest in bundle['manifests'].items():
        if pid!=sha(manifest['protocol']): raise ValueError('Scorer protocol identity changed')
    frozen(folder/'BUNDLE_PLAN.json', bundle)
    previous = chain; results = {}
    for pid, manifest in sorted(bundle['manifests'].items()):
        if not manifest['units']: continue
        options = {'sampler_class': sampler_classes[pid]} if sampler_classes is not None else {}
        results[pid] = execute_judges(previous, folder/pid, manifest, check_release, **options)
        previous = SimpleNamespace(folder=folder/pid)
    return results


def saved_scores(folder, bundle):
    outputs = {}; receipts = {}; folder = Path(folder)
    for pid, manifest in bundle['manifests'].items():
        outputs[pid] = {}; receipts[pid] = {}
        for job in manifest['units']:
            key = sampling_key(job['unit']); base = folder/pid
            path = base/'outputs'/(key+'.json')
            if path.exists(): outputs[pid][key] = read(path)
            visible = base/'execution/visible'/key
            if (visible/'record.json').exists():
                receipts[pid][key] = {name: read(visible/(name+'.json')) for name in ('request', 'record', 'response')}
    return outputs, receipts


def checked_score(category, value):
    if not isinstance(value, dict): raise ValueError('Structured score required')
    if category in PERSIST:
        score = value['rating']; maximum = 3 if category=='beneficial_memory_usage' else 5
        if type(score) is not int or not 1<=score<=maximum: raise ValueError('Invalid Persist rating')
    elif category=='rpeval':
        if (type(value['matched']) is not int or type(value['total']) is not int
                or not 0<=value['matched']<=value['total'] or value['total']<1):
            raise ValueError('Invalid native RPEval counts')
    else:
        for kind in ('aar', 'mr'):
            n, d = value[kind+'_numerator'], value[kind+'_denominator']
            if type(n) is not int or type(d) is not int or not 0<=n<=d:
                raise ValueError('Invalid BenchPreS attribute counts')
        if type(value['task_completeness']) is not int or not 1<=value['task_completeness']<=5:
            raise ValueError('Invalid task completeness')
        if value['aar_denominator']+value['mr_denominator']!=5:
            raise ValueError('Native five-attribute scoring denominator changed')
    return value


def report(chain, cases, methods, bundle, outputs, receipts, protocols, judge_specs, decode):
    if build_judges(chain, cases, methods, protocols, judge_specs)!=bundle:
        raise ValueError('Scorer inputs differ from saved actual Actor answers')
    audited = {pid: audit_receipts(manifest, outputs.get(pid, {}), receipts.get(pid, {}))
               for pid, manifest in bundle['manifests'].items()}
    links = {(r['root_id'], r['method'], r['replicate'], r['stage']): r for r in bundle['assignments']}
    skips = {(r['root_id'], r['method'], r['replicate']): r for r in bundle['skipped_actor_draws']}
    by_method = {}
    for name in methods:
        draw_rows = []; persist_rows = []
        for case in cases:
            ratings = []
            for rep in range(REPEATS[case['category']]):
                slot = case['uid'], name, rep; texts = {}; traces = []; score = None; error = None
                status = skips[slot]['reason'] if slot in skips else 'JUDGE_UNAVAILABLE'
                for stage in stages(case['category']):
                    link = links.get((*slot, stage))
                    if link is None: continue
                    item = audited[link['protocol_id']][link['sample_key']]
                    traces.append({'stage': stage, 'sample_key': link['sample_key'], 'available': item['available']})
                    if item['available']: texts[stage] = item['answer']
                if len(texts)==len(stages(case['category'])):
                    try:
                        score = checked_score(case['category'], decode(case['uid'], case['category'], texts))
                        if (case['category']=='rpeval' and score['total']!=
                                links[(*slot, 'RPEvalJudge')]['expected_metric_items']):
                            raise ValueError('RPEval denominator differs from actual public candidates')
                        status = 'SCORED'
                    except (ValueError, TypeError, KeyError) as exc:
                        error = type(exc).__name__; status = 'JUDGE_CONTRACT_ERROR'; score = None
                if case['category'] in PERSIST: ratings.append(score['rating'] if score is not None else None)
                draw_rows.append({**case, 'method': name, 'replicate': rep, 'status': status,
                                  'score': score, 'score_error_type': error, 'judge_traces': traces})
            if case['category'] in PERSIST: persist_rows.append({**case, 'scores': ratings})
        by_method[name] = {'draw_rows': draw_rows, 'persist_metrics': persist_failure_table(persist_rows),
                          'rpeval_and_benchpres_aggregation': 'Use frozen native manifest/scorer aggregation; no composite here'}
    return {'by_method': by_method, 'generation_plan_sha256': sha(chain.plan), 'judge_bundle_sha256': sha(bundle),
            'native_repeat_dataflow_checked': True, 'native_provider_parity_proven': False,
            'not_a_native_SOTA_claim': True, 'new_model_calls': 0}
