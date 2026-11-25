"""Construct per-question comparison records without inventing causal diagnoses."""
from .pilot_reporting import METHODS


def question_records(cases, rows):
    result=[]
    for case in cases:
        cell={}
        for method in METHODS:
            row=rows.get((case['uid'],method))
            if not row:
                cell[method]={'actor_status':'not_dispatched','score_status':'not_dispatched'}
                continue
            entry={'actor_status':row.get('actor_status'),'score_status':row.get('score_status'),
                   'answer':row.get('answer'),'score':row.get('score'),
                   'error_type':row.get('error_type'),'error':row.get('error')}
            if method=='B2':
                entry['selected']=row.get('gate',{}).get('selected')
            if method=='B3':
                entry['decisions']=row.get('binding',{}).get('decisions')
                entry['bindings']=row.get('binding',{}).get('bindings')
                entry['critical_gaps']=row.get('binding',{}).get('critical_gaps')
            cell[method]=entry
        result.append({'uid':case['uid'],'benchmark':case['benchmark'],'category':case['category'],
                       'root_id':case['root_id'],'query':case['query'],'cells':cell,
                       'causal_attribution':'not established from scores alone'})
    return result
