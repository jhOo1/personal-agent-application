"""Pure, missing-aware summaries for the frozen pilot."""
from collections import defaultdict

METHODS = ('B0', 'B1', 'B2', 'B3')


def metric_values(benchmark, score):
    if benchmark == 'personamem':
        return {'accuracy': score['accuracy']}
    if benchmark == 'memsyco':
        return {k: v for k, v in score.get('metrics', {}).items()
                if isinstance(v, (int, float))}
    if benchmark == 'benchpres':
        return {'task_completeness':score['task_completeness'],
                'aar_numerator':score['aar_numerator'], 'aar_denominator':score['aar_denominator'],
                'mr_numerator':score['mr_numerator'], 'mr_denominator':score['mr_denominator']}
    raise ValueError('unknown benchmark')


def category_coverage(cases, rows):
    groups = defaultdict(lambda: {'planned':0, 'present':0, 'actor_ok':0, 'scored':0, 'metrics':defaultdict(list)})
    for case in cases:
        for method in METHODS:
            group=groups[(case['benchmark'], case['category'], method)]
            group['planned']+=1
            row=rows.get((case['uid'], method))
            if not row:continue
            group['present']+=1
            if row.get('actor_status') == 'ok':group['actor_ok']+=1
            if row.get('score_status') != 'ok':continue
            group['scored']+=1
            for name, value in metric_values(case['benchmark'],row['score']).items():
                group['metrics'][name].append(value)
    result=[]
    for (benchmark, category, method), group in sorted(groups.items()):
        metrics={name:{'n':len(values),'sum':sum(values),'mean':sum(values)/len(values)}
                 for name,values in group['metrics'].items()}
        if benchmark == 'benchpres':
            for name in ('aar','mr'):
                numerator=metrics.get(name+'_numerator',{}).get('sum',0)
                denominator=metrics.get(name+'_denominator',{}).get('sum',0)
                metrics[name]={'n':denominator, 'sum':numerator,
                               'mean':numerator/denominator if denominator else None}
        result.append({'benchmark':benchmark,'category':category,'method':method,
                       'planned':group['planned'],'present':group['present'],
                       'actor_ok':group['actor_ok'],'scored':group['scored'],'metrics':metrics})
    return result


def request_accounting(requests, cache_imports, events=()):
    groups=defaultdict(lambda:{'requests':0,'statuses':defaultdict(int),'known_prompt_tokens':0,
                               'known_completion_tokens':0,'usage_unknown':0})
    for row in requests:
        key=row.get('key','')
        if '/writer' in key: stage='writer'
        elif '/preference_judge/' in key or '/completeness_judge' in key or key.endswith('/judge'):stage='judge'
        elif '/binder' in key:stage='binder'
        elif '/gate' in key:stage='gate'
        elif '/actor' in key:stage='actor'
        else:stage='other'
        group=groups[stage];group['requests']+=1;group['statuses'][row.get('status','unknown')]+=1
        usage=row.get('usage')
        if usage is None:group['usage_unknown']+=1
        else:
            group['known_prompt_tokens']+=usage.get('prompt_tokens',0) or 0
            group['known_completion_tokens']+=usage.get('completion_tokens',0) or 0
    return {'stages':dict(groups),'cache_imports':len(cache_imports),
            'local_cache_hits':sum(e.get('status')=='local_cache_hit' for e in events),
            'imported_cache_hits':sum(e.get('status')=='imported_cache_hit' for e in events),
            'cache_imports_are_new_requests':False}
