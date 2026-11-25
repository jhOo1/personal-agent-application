"""Three-answer BenchPreS grading bound to actual independent Actor receipts.

The caller supplies a frozen evaluation adapter and scorer version. No Gold is
available to generation, no missing answer is fabricated, and provider/Judge
parity is never inferred from a model alias or a successful structural test.
"""
from copy import deepcopy

from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key, validate_public_request
from proposals.qamc_sentence_units.runtime import read
from .native_generation import generation_plan, generation_repeats, BENCHPRES_REPEATS
from .native_judging import audit_receipts
from .native_chain_judging import execute_judges  # Reuse cross-stage pacing/auth protection.

STAGES = tuple(f'BenchAttr{i}' for i in range(5)) + ('BenchComplete',)


def build_judges(chain, cases, methods, protocol, judge_requests):
    allocation = [{k: c[k] for k in ('uid', 'category')} for c in cases]
    if (generation_repeats(chain.plan['protocol']) != BENCHPRES_REPEATS
            or generation_plan(allocation, methods, chain.plan['protocol']) != chain.plan
            or protocol.get('benchmark') != 'benchpres'
            or protocol.get('repeat_policy') != BENCHPRES_REPEATS
            or set(protocol['stages']) != set(STAGES)
            or not isinstance(protocol.get('score_version'), str) or not protocol['score_version']):
        raise ValueError('Frozen BenchPreS three-answer allocation and scorer version required')
    if any(set(c) != {'uid', 'category', 'group_id'}
           or not isinstance(c['group_id'], str) or not c['group_id'] for c in cases):
        raise ValueError('Explicit profile grouping required')
    saved = read(chain.folder / 'GENERATION_RESULT.json')
    if saved['case_allocation'] != allocation:
        raise ValueError('Evaluation roots/category order changed after generation')
    expected = {sampling_key(n['unit']): n['unit'] for n in chain.plan['nodes'] if n['unit']['stage'] == 'Actor'}
    rows = saved['rows']
    if len(rows) != len(expected) or {r['actor_sample_key'] for r in rows} != expected.keys():
        raise ValueError('Missing or duplicate planned Actor slot')
    index = {}
    for row in rows:
        unit = expected[row['actor_sample_key']]
        if any(row[field] != unit[name] for field, name in
               [('uid', 'root_id'), ('method', 'method'), ('replicate', 'replicate')]):
            raise ValueError('Actor belongs to another root, method or replicate')
        index[row['uid'], row['method'], row['replicate']] = row
    jobs, links, skipped = [], [], []
    for case in cases:
        for rep in range(3):
            groups = {}
            for method in methods:
                row = index[case['uid'], method, rep]; key = row['actor_sample_key']
                link = {'root_id': case['uid'], 'method': method, 'replicate': rep, 'actor_sample_key': key}
                if row['status'] == 'UPSTREAM_UNAVAILABLE':
                    if chain.output(key) is not None:
                        raise ValueError('Unavailable upstream unexpectedly has an Actor output')
                    skipped.append({**link, 'reason': 'UPSTREAM_UNAVAILABLE'})
                    continue
                actor = chain.audit(key)
                if not actor['available']:
                    if row['status'] != 'ACTOR_UNAVAILABLE':
                        raise ValueError('Actor availability differs from real receipt')
                    skipped.append({**link, 'reason': 'ACTOR_UNAVAILABLE'})
                    continue
                if row['status'] != 'ANSWER_AVAILABLE' or row['actor_request_sha256'] != actor['request_sha256']:
                    raise ValueError('Actor generation hash or availability mismatch')
                bodies = judge_requests(case['uid'], actor['answer'])
                if set(bodies) != set(STAGES):
                    raise ValueError('Five preference checks and one completeness check required')
                for stage in STAGES:
                    body = bodies[stage]; validate_public_request(body); settings = protocol['stages'][stage]
                    if (body['model'] != protocol['model']
                            or any(body[k] != settings[k] for k in ('temperature', 'max_tokens'))
                            or body.get('stream') is not True
                            or body.get('stream_options') != {'include_usage': True}):
                        raise ValueError('Judge request differs from frozen scorer settings')
                    # Sharing is limited to identical answer checks within the
                    # same root/replicate/stage. Independent draws stay distinct.
                    groups.setdefault((stage, sha(body)), {'request': deepcopy(body), 'links': []})['links'].append(
                        {**link, 'stage': stage, 'actor_answer_sha256': sha(actor['answer'])})
            for (stage, _), group in groups.items():
                identity = {'protocol_sha256': sha(protocol), 'root_id': case['uid'],
                            'method': group['links'][0]['method'], 'replicate': rep, 'stage': stage}
                key = sampling_key(identity)
                jobs.append({'unit': identity, 'request': group['request']})
                links.extend({**link, 'sample_key': key, 'request_sha256': sha(group['request'])}
                             for link in group['links'])
    return {'protocol': deepcopy(protocol), 'units': jobs, 'assignments': links,
            'skipped_upstream_draws': skipped, 'maximum_physical_dispatches': len(jobs),
            'root_count': len(cases), 'planned_actor_draws': len(expected),
            'historical_body_cache': False, 'cross_replicate_body_cache': False,
            'generation_result_sha256': sha(saved), 'chain_plan_sha256': sha(chain.plan),
            'native_judge_provider_parity_proven': False}


def summarize(rows):
    """Keep answer-average and pooled-count metrics distinct; missing is NA."""
    valid = [r['score'] for r in rows if r['score'] is not None]
    means, micro, counts = {}, {}, {}
    for metric in ('aar', 'mr'):
        usable = [s for s in valid if s[metric + '_denominator'] > 0]
        counts[metric.upper()] = len(usable)
        means[metric.upper()] = (sum(s[metric + '_numerator'] / s[metric + '_denominator'] for s in usable)
                                 / len(usable)) if usable else None
        total = sum(s[metric + '_denominator'] for s in usable)
        micro[metric.upper()] = sum(s[metric + '_numerator'] for s in usable) / total if total else None
    means['completeness'] = sum(s['task_completeness'] for s in valid) / len(valid) if valid else None
    counts['completeness'] = len(valid)
    return {'planned_answer_slots': len(rows), 'valid_answer_scores': len(valid),
            'answer_mean': means, 'pooled_preference_micro': micro, 'valid_draws_per_metric': counts}


def report(chain, cases, methods, manifest, outputs, receipts, judge_requests, decode):
    if build_judges(chain, cases, methods, manifest['protocol'], judge_requests) != manifest:
        raise ValueError('Judge manifest differs from actual independent Actor answers')
    audited = audit_receipts(manifest, outputs, receipts)
    links = {(r['root_id'], r['method'], r['replicate'], r['stage']): r for r in manifest['assignments']}
    skips = {(r['root_id'], r['method'], r['replicate']): r for r in manifest['skipped_upstream_draws']}
    result = {}
    for method in methods:
        rows = []
        for case in cases:
            for rep in range(3):
                slot = case['uid'], method, rep; score, error = None, None
                raw, trace = {}, {}
                status = skips[slot]['reason'] if slot in skips else 'JUDGE_UNAVAILABLE'
                if slot not in skips:
                    for stage in STAGES:
                        link = links[(*slot, stage)]; trace[stage] = link['sample_key']
                        if audited[link['sample_key']]['available']:
                            raw[stage] = audited[link['sample_key']]['answer']
                    if len(raw) == len(STAGES):
                        try:
                            score = decode(case['uid'], raw)
                            for metric in ('aar', 'mr'):
                                n, d = score[metric + '_numerator'], score[metric + '_denominator']
                                if type(n) is not int or type(d) is not int or not 0 <= n <= d <= 5:
                                    raise ValueError('Invalid preference count')
                            if (score['aar_denominator'] + score['mr_denominator'] != 5
                                    or type(score['task_completeness']) is not int
                                    or not 1 <= score['task_completeness'] <= 5):
                                raise ValueError('Invalid completeness or five-attribute denominator')
                            status = 'SCORED'
                        except (ValueError, KeyError, TypeError) as exc:
                            score = None; status = 'JUDGE_CONTRACT_ERROR'; error = type(exc).__name__
                rows.append({**case, 'method': method, 'replicate': rep, 'status': status,
                             'score': score, 'score_error_type': error, 'judge_sample_keys': trace})
        complete = {c['uid'] for c in cases if sum(r['uid'] == c['uid'] and r['score'] is not None for r in rows) == 3}
        profiles = sorted({c['group_id'] for c in cases})
        result[method] = {'rows': rows, 'all_available_draws': summarize(rows),
                          'complete_triplet_roots': len(complete),
                          'complete_roots_only': summarize([r for r in rows if r['uid'] in complete]),
                          'by_profile': {g: summarize([r for r in rows if r['group_id'] == g]) for g in profiles},
                          'leave_one_profile_out': {g: summarize([r for r in rows if r['group_id'] != g]) for g in profiles}}
    return {'by_method': result, 'score_version': manifest['protocol']['score_version'],
            'native_judge_provider_parity_proven': False, 'not_a_native_SOTA_claim': True,
            'all_selected_root_count': len(cases), 'answer_draws_per_root': 3,
            'missing_scores_are_not_zero': True, 'new_model_calls': 0}
