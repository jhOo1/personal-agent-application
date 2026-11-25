"""Compare a paper-prompt arm with frozen C5 and Gate on old BenchPreS roots."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import re
import time

import qamc_benchpres_formal_paper_bridge as paper
import qamc_fixed_source_application_run as common
import qamc_paper_baseline_validation_run as base
import qamc_persist_saved_answer_alignment_run as persist
import qamc_rpeval_formal_multi_report as formal_report
import qamc_rpeval_formal_multi_run as formal
from proposals.qamc_memgate_external import evaluation as score
from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.bace.runtime import runner_lock
from qamc.contextual_match.development import text_request
from qamc.contextual_match.evaluation import paired
from qamc.contextual_match.runtime_minute_policy import MinuteControl, activate
from qamc.contextual_match.usage_observability import UsageObservableSampler
from qamc.pa.core import digest
from qamc.transport_helpers import atomic_json, read_reference

ROOT, read, pin, sha = base.ROOT, base.read, formal.pin, base.sha
OUT = base.OUT.parent / 'benchpres_matched_paper_v1'
RUN = ROOT / 'runs' / OUT.parent.name / OUT.name
METHOD = paper.pilot.METHOD
JUDGES = tuple(base.grade_stages({'benchmark': 'benchpres'}))
LIMIT = 336


def block(stage):
    if stage not in ('Actor', *JUDGES):
        raise ValueError('Unknown fixed scoring stage')
    return 'generation' if stage == 'Actor' else 'grading'


def unit(plan, uid, method, stage):
    return {'protocol_sha256': sha(plan['protocols'][block(stage)]), 'root_id': uid,
            'method': method, 'stage': stage, 'replicate': 0}


def job(plan, uid, method, stage, body):
    proto = plan['protocols'][block(stage)]
    if (method != METHOD or body['model'] != proto['model']
            or any(body[k] != v for k, v in proto['stages'][stage].items())):
        raise ValueError('Frozen paper-prompt model or configuration changed')
    return {'unit': unit(plan, uid, method, stage), 'request': body}


def build_plan():
    prior_file = base.OUT / 'PLAN.json'
    prior = read(prior_file)
    profiles_file = base.OUT / 'ANALYSIS_GROUPS.json'
    groups = read(profiles_file)
    if sha(groups) != read(base.OUT / 'ANALYSIS_FREEZE.json')['analysis_groups_sha256']:
        raise ValueError('Original development profile grouping changed')
    profiles = {r['uid']: r['analysis_group_id'] for r in groups['rows']}
    cases = [{**c, 'analysis_group_id': profiles[c['uid']]} for c in prior['cases'] if c['benchmark'] == 'benchpres']
    public, prompts = paper.source_rows()
    defense = paper.pilot.DEFENSE.read_text().strip()
    protocol = deepcopy(prior['protocols'])
    for key, names in (('generation', ('Actor',)), ('grading', JUDGES)):
        protocol[key]['stages'] = {name: protocol[key]['stages'][name] for name in names}
        protocol[key].update(namespace=OUT.parent.name + '/' + OUT.name + '/' + key, stream_cooldown_seconds=60)
    plan = {'protocols': protocol, 'cases': cases, 'methods': [METHOD],
            'maximum_new_physical_requests': LIMIT, 'new_method_candidates': 0, 'new_cases': 0,
            'service_reference_sha256': prior['service_reference_sha256']}
    envelope = {k: v for k, v in read(paper.pilot.OUT / 'PLAN.json')['initial'][0]['request'].items()
                if k != 'messages'}
    envelope.update(model=protocol['generation']['model'], **protocol['generation']['stages']['Actor'])
    jobs = []
    for case in cases:
        index, uid = case['row_index'], case['uid']
        task = base.task_for(case)
        raw = paper.benchpres_public(prompts[index], uid)
        if raw.payload() != task.payload() or sha(raw.payload()) != public[index]['public_input_sha256']:
            raise ValueError('Official public profile or task drift: ' + uid)
        # Only the original public prompt and the fixed paper defense enter this request.
        jobs.append(job(plan, uid, METHOD, 'Actor', paper.request(prompts[index], defense, envelope)))
    old = read(base.OUT / 'RESULT_ROWS.json')
    uids = {c['uid'] for c in cases}
    inherited = [r for r in old if r['uid'] in uids and r['method'] in base.OWN]
    refs = {c['uid']: read(ROOT / c['evaluation_path']) for c in cases}
    for row in inherited:
        if row['score'] is not None and score.grade(ROOT, 'benchpres', refs[row['uid']], row['raw_scores']) != row['score']:
            raise ValueError('Archived control grading does not exactly replay')
        req = row.get('actor_request')
        actor_settings = protocol['generation']['stages']['Actor']
        if req and any(req[k] != envelope[k] for k in ('model', *actor_settings)):
            raise ValueError('Inherited generation settings differ')
    paths = [Path(__file__).resolve(), Path(score.__file__).resolve(), Path(paper.__file__).resolve(),
             Path(paper.pilot.__file__).resolve(), paper.pilot.DEFENSE, paper.CATALOG, paper.NATIVE_SOURCE,
             paper.pilot.OUT / 'PLAN.json', prior_file, base.OUT / 'RESULT_ROWS.json',
             base.OUT / 'PUBLIC_TASKS.json', profiles_file, base.OUT / 'ANALYSIS_FREEZE.json', OUT / 'RULES.md',
             *(ROOT / c['evaluation_path'] for c in cases)]
    inherited_fields = ('uid', 'method', 'benchmark', 'actor_status', 'actor_request_sha256', 'score')
    plan.update(initial_requests=jobs,
                inherited_scores=[{key: row.get(key) for key in inherited_fields} for row in inherited],
                allowed_unit_keys=[sampling_key(unit(plan, c['uid'], METHOD, stage))
                                   for c in cases for stage in ('Actor', *JUDGES)],
                files={str(p.relative_to(ROOT)): pin(p) for p in paths})
    check(plan, False)
    return plan


def check(plan, service=True):
    cases = plan['cases']
    if (len(cases) != 48 or len({c['analysis_group_id'] for c in cases}) != 10
            or plan['new_cases'] or plan['new_method_candidates'] or len(plan['inherited_scores']) != 96
            or plan['maximum_new_physical_requests'] != LIMIT or len(set(plan['allowed_unit_keys'])) != LIMIT
            or len(plan['initial_requests']) != len(cases)):
        raise ValueError('Development allocation changed')
    for name, digest_file in plan['files'].items():
        if pin(ROOT / name) != digest_file:
            raise ValueError('Frozen input changed: ' + name)
    if service and read_reference()[1] != plan['service_reference_sha256']:
        raise ValueError('Frozen service reference changed')


def grade_jobs(plan, rows):
    by = {c['uid']: c for c in plan['cases']}
    jobs, refs = [], {}
    proto = plan['protocols']['grading']
    for row in rows:
        if row['actor_status'] != 'OK' or not row.get('answer'):
            continue
        uid = row['uid']
        case = by[uid]
        reference = read(ROOT / case['evaluation_path'])
        if digest(reference) != case['evaluation_hash']:
            raise ValueError('Evaluation reference changed')
        refs[uid] = reference
        query = base.task_for(case).query
        for stage, system, payload in score.initial_requests(ROOT, 'benchpres', reference, query, row['answer']):
            jobs.append(job(plan, uid, METHOD, stage, text_request(system, payload, proto['model'],
                                                                   proto['stages'][stage]['max_tokens'])))
    return jobs, refs


def engine(plan, run_path=RUN, offline=False):
    ex = common.Dispatcher(ROOT, OUT, run_path, plan,
        (lambda p: check(p, False)) if offline else check, job, block)
    receipts = formal.previous.spec.prior.receipts(run_path)
    if any(r['status'] == 'PENDING_DELIVERY_UNKNOWN' for r in receipts):
        raise ValueError('Inspect delivery of previously registered requests')
    activate(ex.gate, max((r['started_unix'] + (r.get('elapsed_seconds') or 0)
                          for r in receipts if r['status'] != 'OK'), default=0))

    def sampler(*args, **kwargs):
        value = UsageObservableSampler(*args, **kwargs)
        value.control = MinuteControl(value.control, ex.gate)
        return value

    for rt in ex.rt.values():
        rt.sampler_class = sampler
    return ex


def evaluate(plan, ex):
    rows = []
    for initial in plan['initial_requests']:
        value = ex.observed(initial)
        rows.append({'uid': initial['unit']['root_id'], 'method': METHOD, 'benchmark': 'benchpres',
                     'actor_status': value['status'] if value else 'UNISSUED',
                     'answer': value['response']['answer'] if value and value['status'] == 'OK' else None,
                     'actor_request_sha256': sha(initial['request']), 'score': None})
    jobs, refs = grade_jobs(plan, rows)
    ex.dispatch('paper_qwen_common_grading', jobs)
    for row in rows:
        uid = row['uid']
        scores = {j['unit']['stage']: ex.observed(j) for j in jobs if j['unit']['root_id'] == uid}
        row['judge_statuses'] = {s: v['status'] if v else 'UNISSUED' for s, v in scores.items()}
        if set(scores) != set(JUDGES) or not all(v and v['status'] == 'OK' for v in scores.values()):
            continue
        raw = {s: v['response']['answer'] for s, v in scores.items()}
        row['raw_scores'] = raw
        try:
            row['score'] = score.grade(ROOT, 'benchpres', refs[uid], raw)
        except (ValueError, TypeError, KeyError) as error:
            row['score_error'] = str(error)
    return rows


def summarize(plan, rows):
    combined = [*plan['inherited_scores'], *rows]
    pairs = []
    index = {(r['uid'], r['method']): r.get('score') for r in combined}
    for own in base.OWN:
        pair = paired(combined, plan['cases'], METHOD, own, 'benchpres')
        common_ids = pair['uids']
        for method in (METHOD, own):
            decisions = [d for uid in common_ids for d in index[uid, method]['decisions']
                         if not re.search(r'\bbold\s+text\b', d['preference'], re.I)]
            pair.setdefault('non_bold', {})[method] = {
                'aar': [sum(d['appropriate'] and d['label'] == 'follow' for d in decisions),
                        sum(d['appropriate'] for d in decisions)],
                'mr': [sum(not d['appropriate'] and d['label'] == 'follow' for d in decisions),
                       sum(not d['appropriate'] for d in decisions)]}
        pairs.append(pair)
    return {'pairs': pairs, 'new_method': METHOD,
            'track': 'BENCHPRES_FIXED_DEVELOPMENT_QWEN_T0_SINGLE_DRAW',
            'model_dispatched_only_for_paper_baseline': True}


def pilot(plan):
    with runner_lock(formal.RUN / 'runner.lock'), runner_lock(RUN / 'runner.lock'):
        if read(formal.OUT / 'RUN_STATE.json')['phase'] != 'FORMAL_TERMINAL':
            raise ValueError('RPEval still owns shared dispatch capacity')
        path = OUT / 'RUN_STATE.json'
        if path.exists() and read(path)['phase'] == 'DEV_TERMINAL':
            raise ValueError('Completed scores cannot be rerun')
        check(plan)
        cumulative = formal_report.snapshot()[0]['cumulative']
        preceding = persist.OUT / 'CALLS.json'
        if preceding.exists():
            cumulative = read(preceding)['cumulative_v2']
        ex = engine(plan)
        ex.dispatch('paper_t0_actors', plan['initial_requests'])
        rows = evaluate(plan, ex)
        formal.frozen(OUT / 'RESULT_ROWS.json', rows)
        formal.frozen(OUT / 'SUMMARY.json', summarize(plan, rows))
        receipts = formal.previous.spec.prior.receipts(RUN)
        count = len(receipts)
        tokens = sum((r.get('usage') or {}).get('total_tokens', 0) for r in receipts)
        unknown = sum('total_tokens' not in (r.get('usage') or {}) for r in receipts)
        formal.frozen(OUT / 'CALLS.json', {'registered_requests': count, 'maximum': LIMIT,
            'states': dict(Counter(r['status'] for r in receipts)),
            'reported_tokens': tokens, 'unknown_usage': unknown,
            'automatic_retries': sum(r.get('automatic_retries', 0) for r in receipts),
            'cumulative_v2': {**cumulative, 'total_physical_requests': cumulative['total_physical_requests'] + count,
                'known_total_tokens': cumulative['known_total_tokens'] + tokens,
                'settled_unknown_total_usage': cumulative['settled_unknown_total_usage'] + unknown}})
        for block_dir in ('generation', 'grading'):
            (RUN / block_dir).mkdir(parents=True, exist_ok=True)
            (RUN / block_dir / 'STOP').write_text('Fixed paper-prompt comparison complete.\n')
        atomic_json(path, {'phase': 'DEV_TERMINAL', 'pid': None, 'updated_unix': time.time(), 'goal_complete': False})


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('prepare', 'pilot'))
    action = cli.parse_args().action
    path = OUT / 'PLAN.json'
    if not path.exists():
        formal.frozen(path, build_plan())
    plan = read(path)
    check(plan, False)
    if action == 'pilot':
        pilot(plan)
    else:
        print({'existing_development_roots': len(plan['cases']), 'paper_generation_positions': 48,
               'max_scoring_positions': 288, 'new_model_calls': 0})
