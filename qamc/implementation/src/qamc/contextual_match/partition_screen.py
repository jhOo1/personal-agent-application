"""Lexical split diagnostics only; never a memory selector or model feature.

Fixed historical screening thresholds are not optimized for capacity or scores.
Passing exact/lexical checks does not certify semantic or human independence.
"""
from difflib import SequenceMatcher

QUERY_THRESHOLD=.72
MEMORY_THRESHOLD=.85


def query_maxima(queries,blocked):
    old=sorted(set(blocked))
    return [max((SequenceMatcher(None,q,v,autojunk=False).ratio() for v in old),default=None) for q in queries]


def memory_maxima(groups,blocked):
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    old=sorted(set(blocked));new=sorted({m for group in groups for m in group})
    if not old or not new:return [None for _ in groups]
    index=TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=1).fit_transform(old+new)
    maxima=np.asarray((index[len(old):]@index[:len(old)].T).max(axis=1).toarray()).ravel()
    values=dict(zip(new,map(float,maxima),strict=True))
    return [max((values[m] for m in group),default=None) for group in groups]


def screen_rows(rows,patterns):
    candidates=[r for r in rows if r['population']=='official' and r['preliminary_unobserved_upper_bound']]
    blocked=[r for r in rows if not r['preliminary_unobserved_upper_bound']]
    result=[]
    for benchmark in ('rpeval','benchpres','persistbench'):
        chosen=[r for r in candidates if r['benchmark']==benchmark]
        old=[r for r in blocked if r['benchmark']==benchmark]
        query=lambda r:patterns[r['query_probe']]
        memories=lambda r:[patterns[key] for key in r['memory_probes']]
        qnear=query_maxima([query(r) for r in chosen],[query(r) for r in old])
        mnear=memory_maxima([memories(r) for r in chosen],[m for r in old for m in memories(r)])
        for row,q,m in zip(chosen,qnear,mnear,strict=True):
            reasons=[]
            if q is None:reasons.append('NO_QUERY_REFERENCE_FOR_SCREENING')
            elif q>=QUERY_THRESHOLD:reasons.append('NEAR_BLOCKED_QUERY')
            if m is None:reasons.append('NO_MEMORY_REFERENCE_FOR_SCREENING')
            elif m>=MEMORY_THRESHOLD:reasons.append('NEAR_BLOCKED_SOURCE')
            result.append({'source_id':row['source_id'],'benchmark':benchmark,'audit_group_id':row['audit_group_id'],
                'track':row.get('track'),'category':row.get('category'),'nearest_blocked_query':q,
                'nearest_blocked_memory':m,'direct_rejection_reasons':reasons})
    blocked_groups={r['audit_group_id'] for r in result if r['direct_rejection_reasons']}
    for row in result:
        row['group_rejected']=row['audit_group_id'] in blocked_groups
        row['lexically_screened_upper_bound']=not row['group_rejected']
        row['certified_independent']=False
    return result
