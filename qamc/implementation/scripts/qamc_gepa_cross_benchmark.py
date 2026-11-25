"""Finish a strong released baseline on the fixed29exposed roots, max72new."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import argparse
import time

import qamc_conditional_transfer_run as prior
import qamc_opponent_native_refresh as opponents
from qamc.common import sha
from qamc.contextual_match import gepa_unified as candidate
from qamc.contextual_match.persist_author_bridge import PersistAuthorBridge
from qamc.transport_helpers import atomic_json
from qamc.bace.runtime import runner_lock
from qamc.contextual_match.lossless_transport import LosslessNativeSampler
from qamc.contextual_match.runtime_minute_policy import activate, MinuteControl

spec = prior.spec;ROOT = spec.ROOT;OUT = spec.BASE/'gepa_cross_benchmark_v1';RUN = ROOT/'runs'/spec.BASE.name/OUT.name
METHOD = 'GEPA_UNIFIED';read, frozen = spec.read, spec.frozen


def prepare():
    if (OUT/'PLAN.json').exists():p = read(OUT/'PLAN.json');check(p, False);return p
    old = spec.prepare();prior.check(old, False)
    if read(spec.OUT/'RUN_STATE.json')['phase'] != 'DEV_TERMINAL':raise ValueError('Prior experiment not terminal')
    bridge = PersistAuthorBridge(ROOT/'literature/qamc_pa_v1/PersistBench')
    history = [r for r in read(opponents.OUT/'RESULT_ROWS.json') if r['method'] == 'PB_GEPA']
    if len(history) != 13:raise ValueError('Expected all thirteen saved Persist controls including failures')
    cases = deepcopy(old['cases']);lookup = {r['uid']: r for r in history}
    p = {'cases': cases, 'methods': [METHOD], 'protocols': deepcopy(old['protocols']),
         'maximum_new_physical_requests': 72, 'new_algorithm_candidates': 0,
         'stage_type': 'bounded strong baseline completion,not another algorithm candidate',
         'service_reference_sha256': old['service_reference_sha256'], 'not_confirmation': True,
         'parent_first_candidate_cost_not_reset': 177, 'parent_first_candidate_cap_unchanged': 304,
         'separate_baseline_budget': True, 'no_selector_or_store_calls': True}
    for key in p['protocols']:p['protocols'][key]['namespace'] = spec.BASE.name+'/'+OUT.name+'/'+key
    initial = [];keys = [];inherited = [];public = {};witness = []
    for c in cases:
        task = spec.prior.parent.task_for(c);public[task.uid] = task.payload();built = candidate.actor(task, bridge)
        if c['uid'] in lookup:
            original = lookup[c['uid']]
            if built['request'] != original['actor_request']:raise ValueError('Completed baseline wire mismatch;no silent reuse')
            row = deepcopy(original);row.update(method=METHOD, original_method='PB_GEPA',
                inherited_without_new_actor_or_judge=True, unified_view=built['view'])
            inherited.append(row);witness.append({'uid':c['uid'],'request_sha256':sha(built['request']),
                'score_available':row.get('score') is not None,'failed_or_missing_not_retried':True});continue
        initial.append(spec.job(p, task.uid, METHOD, 'Actor', built['request']))
        stages = ['Actor', *(['RPEvalJudge'] if c['benchmark'] == 'rpeval' else [*(f'BenchAttr{i}' for i in range(5)), 'BenchComplete'])]
        for stage in stages:keys.append(spec.prior.parent.sampling_key(spec.unit(p, task.uid, METHOD, stage)))
    if len(initial) != 16 or len(keys) != 72:raise ValueError('Baseline extension allocation differs')
    p.update(initial_requests=initial, allowed_unit_keys=sorted(keys))
    frozen(OUT/'BASELINE_ROWS.json', inherited);frozen(OUT/'PUBLIC_INPUTS.json', public)
    frozen(OUT/'REUSE_WITNESSES.json', witness)
    frozen(OUT/'AUTHOR_MANIFEST.json', {'pinned_author_bridge':bridge.manifest(),
        'current_actual_actor':'qwen3.8-flash','current_actual_judge':'qwen3.8-flash',
        'historical_bridge_development_defaults_not_current_runtime':True})
    frozen(OUT/'PROMPT_TEMPLATE.json', bridge.blobs['GEPA'].decode())
    files = [Path(__file__),Path(candidate.__file__),ROOT/'tests/test_qamc_gepa_unified.py',OUT/'RULES.md',
             OUT/'BASELINE_ROWS.json',OUT/'PUBLIC_INPUTS.json',OUT/'REUSE_WITNESSES.json',OUT/'AUTHOR_MANIFEST.json',OUT/'PROMPT_TEMPLATE.json',
             opponents.OUT/'RESULT_ROWS.json',spec.OUT/'AUTHORIZATION.json']
    p['files'] = {str(f.relative_to(ROOT)):prior.pin(f) for f in files}
    frozen(OUT/'PLAN.json', p);check(p, False);return p


def check(p, service=True):
    prior.check(spec.prepare(), service)
    if len(p['allowed_unit_keys']) != 72 or p['maximum_new_physical_requests'] != 72:raise ValueError('Separate baseline cap changed')
    for path, value in p['files'].items():
        if prior.pin(ROOT/path) != value:raise ValueError('Frozen file drift: '+path)


def engine(p, path=None):
    ex = spec.prior.parent.Dispatcher(ROOT, OUT, path or RUN, p, check, spec.job, prior.block)
    rec = spec.prior.receipts(ex.run)
    if any(r['status'] == 'PENDING_DELIVERY_UNKNOWN' for r in rec):raise ValueError('Retain unknown requests;no blind replay')
    activate(ex.gate, max((r['started_unix']+r.get('elapsed_seconds',0) for r in rec if r['status'] != 'OK'),default=0))
    def sampler(*a,**kw):
        s = LosslessNativeSampler(*a,**kw);s.control = MinuteControl(s.control,ex.gate);return s
    for rt in ex.rt.values():rt.sampler_class = sampler
    return ex


def main(action):
    p = prepare();check(p, action == 'run')
    if action == 'prepare':print({'new_http':0,'maximum_new':72,'inherited':13,'new_actors':16});return
    if (OUT/'RUN_STATE.json').exists() and read(OUT/'RUN_STATE.json')['phase'] == 'DEV_TERMINAL':raise ValueError('Baseline already terminal')
    with runner_lock(RUN/'runner.lock'):
        ex = engine(p);rows = deepcopy(read(OUT/'BASELINE_ROWS.json'))
        bridge = PersistAuthorBridge(ROOT/'literature/qamc_pa_v1/PersistBench');cases = {c['uid']:c for c in p['cases']}
        ex.dispatch('unissued_baseline_actors',p['initial_requests'])
        for j in p['initial_requests']:
            uid = j['unit']['root_id'];built = candidate.actor(spec.prior.parent.task_for(cases[uid]),bridge);value = ex.observed(j)
            row = {'uid':uid,'benchmark':cases[uid]['benchmark'],'method':METHOD,'read_status':'NOT_REQUIRED',
                'actor_status':value['status'] if value else 'UNISSUED','score':None,'raw_scores':{},
                'actor_request':j['request'],'actor_request_sha256':sha(j['request']),'view':built['view'],'input_audit':built['audit']}
            if value and value['status'] == 'OK':row['answer'] = value['response']['answer']
            rows.append(row)
        frozen(OUT/'ANSWER_CHECKPOINT.json',rows)
        changed = [r for r in rows if not r.get('inherited_without_new_actor_or_judge')]
        jobs,refs,_ = spec.prior.parent.legacy.grading.grade_jobs(p,p['cases'],changed);ex.dispatch('unissued_baseline_grades',jobs)
        for row in changed:
            selected = [j for j in jobs if j['unit']['root_id'] == row['uid']]
            values = {j['unit']['stage']:ex.observed(j) for j in selected};row['judge_statuses'] = {k:v['status'] if v else 'UNISSUED' for k,v in values.items()}
            if not selected or not all(v and v['status'] == 'OK' for v in values.values()):continue
            raw = {k:v['response']['answer'] for k,v in values.items()};row['raw_scores'] = raw;c = cases[row['uid']]
            try:
                if c['benchmark'] == 'benchpres':row['score'] = spec.prior.parent.legacy.ext.grade(ROOT,'benchpres',refs[row['uid']],raw)
                else:
                    ref = refs[row['uid']];multi = isinstance(ref['persona'],list)
                    row['score'] = {**spec.prior.parent.legacy.ext.parse_score(spec.prior.parent.legacy.ext.parse_object(raw['RPEvalJudge']),len(ref['persona']) if multi else 1,multi),
                        'judge_variant':'archived_rubric_QWEN_8192','fully_official':False}
            except (ValueError,TypeError,KeyError) as e:row['score_error'] = str(e)
        frozen(OUT/'RESULT_ROWS.json',rows);rec = spec.prior.receipts(RUN)
        frozen(OUT/'CALLS.json',{'physical_requests':len(rec),'statuses':dict(Counter(v['status'] for v in rec)),
            'reported_tokens':sum((v.get('usage') or {}).get('total_tokens',0) for v in rec),
            'unknown_usage':sum('total_tokens' not in (v.get('usage') or {}) for v in rec),'maximum':72,'algorithm_candidate_count_increment':0})
        for k in p['protocols']:(RUN/k/'STOP').write_text('Finite released-baseline completion terminal.\n')
        atomic_json(OUT/'RUN_STATE.json',{'phase':'DEV_TERMINAL','pid':None,'goal_complete':False,'updated_unix':time.time()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);main(parser.parse_args().action)
