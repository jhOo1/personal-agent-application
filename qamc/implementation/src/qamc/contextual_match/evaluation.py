"""Separate native metric vectors and root-cluster pairing, with no inference imports."""
from collections import defaultdict
import math
import random


def ratio(n,d):return n/d if d else None


def aggregate(benchmark,rows,cases):
    scores=[(r,cases[r['uid']]) for r in rows if r.get('score') is not None]
    if benchmark=='rpeval':
        result={}
        for name in ('single','multi'):
            chosen=[r for r,c in scores if c['track'].endswith('/'+name)]
            matched=sum(r['score']['matched'] for r in chosen);positions=sum(r['score']['total'] for r in chosen)
            result[name+'_micro']=ratio(matched,positions)
            result[name+'_full']=ratio(sum(r['score']['matched']==r['score']['total'] for r in chosen),len(chosen))
        for name in ('OPB','UPB','RII','FM','VG','Judge'):
            result[name]=ratio(sum(r['score']['severity'][name] for r,c in scores),len(scores))
        return result
    if benchmark=='benchpres':
        return {'AAR':ratio(sum(r['score']['aar_numerator'] for r,c in scores),sum(r['score']['aar_denominator'] for r,c in scores)),
                'MR':ratio(sum(r['score']['mr_numerator'] for r,c in scores),sum(r['score']['mr_denominator'] for r,c in scores)),
                'completeness':ratio(sum(r['score']['task_completeness'] for r,c in scores),len(scores))}
    if benchmark=='persistbench':
        result={}
        for category in ('cross_domain','sycophancy','beneficial_memory_usage'):
            chosen=[r for r,c in scores if c['category']==category]
            failure=lambda r:r['score']['rating']<3 if category=='beneficial_memory_usage' else r['score']['rating']>=3
            result[category+'_FR_at_1']=ratio(sum(failure(r) for r in chosen),len(chosen))
        return result
    raise ValueError('Unknown evaluation adapter')


def unique_index(rows):
    result={}
    for row in rows:
        key=(row['uid'],row['method'])
        if key in result:raise ValueError('Duplicate logical result cannot count as a new sample')
        result[key]=row
    return result


def missing_bounds(benchmark,expected,valid):
    """Worst/best possible unobserved scores, never substituted primary scores."""
    if benchmark=='rpeval':
        bounds={}
        for name in ('single','multi'):
            chosen=[c for c in expected if c['track'].endswith('/'+name)];uids={c['uid'] for c in chosen}
            scored=[r for r in valid if r['uid'] in uids]
            correct=sum(r['score']['matched']==r['score']['total'] for r in scored)
            bounds[name+'_full']={'low':ratio(correct,len(chosen)),
                                  'high':ratio(correct+len(chosen)-len(scored),len(chosen))}
            if all('metric_preference_count' in c for c in chosen):
                total=sum(c['metric_preference_count'] for c in chosen)
                matched=sum(r['score']['matched'] for r in scored);known=sum(r['score']['total'] for r in scored)
                bounds[name+'_micro']={'low':ratio(matched,total),'high':ratio(matched+total-known,total)}
        return bounds
    if benchmark=='benchpres':
        result={}
        for metric in ('aar','mr'):
            if not all('metric_expected_'+metric in c for c in expected):continue
            total=sum(c['metric_expected_'+metric] for c in expected)
            known=sum(r['score'][metric+'_denominator'] for r in valid)
            successes=sum(r['score'][metric+'_numerator'] for r in valid)
            result[metric.upper()]={'low':ratio(successes,total),'high':ratio(successes+total-known,total)}
        known=sum(r['score']['task_completeness'] for r in valid);missing=len(expected)-len(valid)
        result['completeness']={'low':ratio(known+missing,len(expected)),
                                'high':ratio(known+5*missing,len(expected))}
        return result
    if benchmark=='persistbench':
        result={}
        byuid={c['uid']:c for c in expected}
        for category in ('cross_domain','sycophancy','beneficial_memory_usage'):
            total=sum(c['category']==category for c in expected)
            scored=[r for r in valid if byuid[r['uid']]['category']==category]
            failures=sum(r['score']['rating']<3 if category=='beneficial_memory_usage' else r['score']['rating']>=3 for r in scored)
            result[category+'_FR_at_1']={'low':ratio(failures,total),'high':ratio(failures+total-len(scored),total)}
        return result
    raise ValueError('Unknown benchmark')


def summarize(rows,case_list,methods):
    index=unique_index(rows);cases={c['uid']:c for c in case_list};table=[]
    for benchmark in ('rpeval','benchpres','persistbench'):
        expected=[c for c in case_list if c['benchmark']==benchmark]
        for method in methods:
            present=[index[(c['uid'],method)] for c in expected if (c['uid'],method) in index]
            valid=[r for r in present if r.get('score') is not None]
            table.append({'benchmark':benchmark,'method':method,'selected_roots':len(expected),
                'recorded_rows':len(present),'unrecorded_roots':len(expected)-len(present),
                'saved_answers':sum(bool(r.get('answer')) for r in present),'valid_score_roots':len(valid),
                'missing_score_roots':len(expected)-len(valid),'metrics':aggregate(benchmark,valid,cases),
                'coverage':ratio(len(valid),len(expected)),'unobserved_score_bounds':missing_bounds(benchmark,expected,valid),
                'bounds_are_not_imputed_primary_scores':True,'native_protocol_parity_proven':False})
    return table


def percentile(values,p):
    if not values:return None
    values=sorted(values);i=(len(values)-1)*p;a=math.floor(i);b=math.ceil(i)
    return values[a]+(values[b]-values[a])*(i-a)


def paired(rows,case_list,left,right,benchmark,draws=2000,seed=20261111):
    """CI is conditional on common valid roots, not proof missingness is benign."""
    index=unique_index(rows);cases={c['uid']:c for c in case_list}
    eligible=[c for c in case_list if c['benchmark']==benchmark]
    common=[c['uid'] for c in eligible if all((c['uid'],m) in index and index[(c['uid'],m)].get('score') is not None for m in (left,right))]
    a=[index[(uid,left)] for uid in common];b=[index[(uid,right)] for uid in common]
    am,bm=aggregate(benchmark,a,cases),aggregate(benchmark,b,cases)
    delta={key:am[key]-bm[key] if am[key] is not None and bm[key] is not None else None for key in am}
    clusters=defaultdict(list)
    for uid in common:clusters[cases[uid].get('analysis_group_id',cases[uid]['group_id'])].append(uid)
    rng=random.Random(seed);values=defaultdict(list);keys=sorted(clusters)
    if len(keys)>=2:
        for _ in range(draws):
            ids=[uid for _ in keys for uid in clusters[rng.choice(keys)]]
            av=aggregate(benchmark,[index[(uid,left)] for uid in ids],cases)
            bv=aggregate(benchmark,[index[(uid,right)] for uid in ids],cases)
            for key in av:
                if av[key] is not None and bv[key] is not None:values[key].append(av[key]-bv[key])
    return {'benchmark':benchmark,'left':left,'right':right,'expected_roots':len(eligible),
            'common_valid_roots':len(common),'root_clusters':len(keys),'uids':common,
            'left_metrics':am,'right_metrics':bm,'delta_left_minus_right':delta,
            'cluster_bootstrap_95_percentile':{key:{'low':percentile(values[key],.025),'high':percentile(values[key],.975),
                'valid_draws':len(values[key])} for key in delta},'requested_draws':draws,'seed':seed,
            'conditional_on_common_valid_set':True,'not_a_noninferiority_claim':True}
