"""Reconstruct fixed original plans, Self-ReCheck evidence and interface inputs."""
from collections import Counter, defaultdict
import json

# Load the local metrics first; several research directories contain a summarize module.
from joint_context import SCOPE, PARENT, metrics, prepare as fit, sha
from baselines import BASE
from expansion_audit import manifest
from expansion_run import OUT as EXPANSION
from exposure_controls import OUT as EXPOSURE, assemble, read, replace_sources
from self_recheck import OUT as DIRECT_ARCHIVE
from trial import ACTOR, wire

MODELS = {'Q':'qwen3.8-flash', 'D':'deepseek-v4.1-flash'}
INTERFACES = ('PLAN','DIRECT')
HISTORY = ('SELECTED','OFF')
ARMS = tuple(f'{model}/{interface}/{history}' for model in MODELS
             for interface in INTERFACES for history in HISTORY)
DIRECT_PROMPT = ACTOR.replace(
    'Use the plan as guidance. Verify any suggestion in it against the current task and supplied original memory. ',
    'Use the selected historical evidence where it is applicable. ')


def direct_from_plan(plan):
    data = json.loads(plan['messages'][1]['content'])
    return wire(DIRECT_PROMPT, dict(task=data['task'], source_evidence=data['source_evidence']),
                plan['max_tokens'])


def bench_cases():
    _, cards, wires, original, _, _ = fit()
    old_direct = {r['uid']:r for r in read(DIRECT_ARCHIVE/'RESULTS.json')['rows']}
    recorded = manifest(DIRECT_ARCHIVE,'Actor')
    plan_dir = SCOPE.with_name(SCOPE.name.split('_actor_mutation')[0]+'_task_only')
    frozen_plans = set()
    for item in manifest(plan_dir,'Plan').values():
        obj = json.loads(item['messages'][1]['content'])
        if set(obj) != {'task'}:
            raise ValueError('Historical fit plan exposed history')
        frozen_plans.add(sha(item))
    prior_plans = {}
    for path in (plan_dir/'Plan/visible').glob('*/record.json'):
        receipt = read(path)
        if receipt['status'] == 'OK' and receipt['request_sha256'] in frozen_plans:
            prior_plans[receipt['unit']['root_id']] = read(path.with_name('response.json'))['answer']
    out = []
    for card in cards:
        if card['domain'] != 'BenchPreS':
            continue
        uid = card['uid']
        direct = recorded.get((uid,'SELF_RECHECK'))
        if direct is None or uid not in wires or old_direct[uid]['actor_status'] != 'OK':
            continue
        plan_input = wires[uid]
        if direct_from_plan(plan_input) != direct:
            raise ValueError('Bench fit Scope and Self-ReCheck evidence differ')
        payload = json.loads(plan_input['messages'][1]['content'])
        if uid not in prior_plans or payload['plan'] != prior_plans[uid]:
            continue
        out.append(dict(card=card,plan=plan_input,direct=direct,
                        archive={'PLAN':original[uid],'DIRECT':old_direct[uid]}))
    return out


def select(exposure_batches):
    labels = {r['uid']:r['labels'] for r in read(
        BASE/'ipe_c_two_endpoint_completion_v1'/'RESULTS.json')['rows']}
    exposure_pool = defaultdict(list)
    for index,batch in enumerate(exposure_batches,1):
        direct_rows = {r['uid']:r for r in read(EXPANSION/f'batch_{index}'/'RESULTS.json')['rows']
                       if r['method'] == 'DIRECT'}
        direct_wires = manifest(EXPANSION/f'batch_{index}','Actor')
        off = {r['uid']:r for r in read(EXPOSURE/f'batch_{index}'/'RESULTS.json')['rows']
               if r['method'] == 'OFF'}
        for bundle in batch:
            card = bundle['card']
            uid,domain,stratum = (card[k] for k in ('uid','domain','stratum'))
            if domain == 'BenchPreS' or not bundle['actors'] or (uid,'DIRECT') not in direct_wires:
                continue
            plan = bundle['actors']['SELECTED']
            direct = direct_wires[uid,'DIRECT']
            if direct_from_plan(plan) != direct:
                raise ValueError('Published Direct lineage mismatch')
            data = json.loads(plan['messages'][1]['content'])
            source_ids = {source['memory_id'] for source in data['source_evidence']}
            legal = []
            if domain == 'RPEval':
                legal = [source['memory_id'] for source,state in zip(
                    card['payload']['source_evidence'],labels[uid],strict=True) if state in 'BC']
            if domain == 'RPEval' and stratum != 'all_A':
                sub = 'delivered' if source_ids.intersection(legal) else 'missing'
            else:
                sub = 'nonempty' if source_ids else 'empty'
            exposure_pool[domain,stratum,sub].append(dict(
                card=card,plan=plan,direct=direct,
                archive={'PLAN':bundle['selected'],'DIRECT':direct_rows[uid],'OFF_PLAN':off[uid]}))
    # Prefer actual competing exposures before adding empty or missing-source controls.
    target = [
        ('RPEval','all_A','nonempty',3), ('RPEval','all_A','empty',1),
        ('RPEval','B_only','delivered',2),
        ('RPEval','contains_C','delivered',2),
        ('PersistBench','cross_domain','nonempty',2),
        ('PersistBench','sycophancy','nonempty',2),
        ('PersistBench','beneficial_memory_usage','nonempty',2),
    ]
    roster, groups = [],set()
    for domain,stratum,sub,count in target:
        pool = sorted(exposure_pool[domain,stratum,sub],
                      key=lambda x:sha(['bic-roster-v1',x['card']['uid']]))
        picked = 0
        for item in pool:
            group = domain,item['card']['group']
            if group in groups:
                continue
            groups.add(group)
            roster.append({**item,'source_role':sub})
            picked += 1
            if picked == count:
                break
        if picked < count:
            raise ValueError(f'Insufficient precise sources {domain}/{stratum}/{sub}: {picked}/{count}')
    bench = sorted(bench_cases(), key=lambda x:sha(['bic-roster-v1',x['card']['uid']]))
    picked = 0
    for item in bench:
        group = 'BenchPreS',item['card']['group']
        selected = bool(json.loads(item['plan']['messages'][1]['content'])['source_evidence'])
        if group in groups or not selected:
            continue
        groups.add(group)
        roster.append({**item,'source_role':'nonempty'})
        picked += 1
        if picked == 4:
            break
    if picked != 4:
        raise ValueError('Require four different archived BenchPreS profiles with actual evidence')
    if len(roster) != 18 or len(groups) != 18:
        raise ValueError('Unexpected enrollment')
    return roster


def variants(item):
    output = {}
    for model,alias in MODELS.items():
        for interface in INTERFACES:
            original = item['plan'] if interface == 'PLAN' else item['direct']
            if (original['model'] != MODELS['Q'] or original['max_tokens'] != 8192
                    or original['temperature'] != 0):
                raise ValueError('Unexpected generation settings')
            for history in HISTORY:
                request = original if history == 'SELECTED' else replace_sources(original,[])
                output[f'{model}/{interface}/{history}'] = {**request,'model':alias}
    return output


if __name__ == '__main__':
    batches,_,_ = assemble()
    roster = select(batches)
    print(json.dumps({
        'assigned':dict(Counter(x['card']['domain'] for x in roster)),
        'exposure_strata':dict(Counter('/'.join((x['card']['domain'],x['card']['stratum'],x['source_role']))
                                       for x in roster)),
        'logical_wires':len(roster)*len(ARMS),
        'unique_wires':len({sha(req) for item in roster for req in variants(item).values()}),
    },indent=2))
