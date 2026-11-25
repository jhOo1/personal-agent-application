#!/usr/bin/env python3
"""Evaluation-only predicted-intent diagnostic, never an inference input."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/qamc_rpreasoner'
RUN=ROOT/'runs/qamc_rpreasoner/execution'
LABELS={'ignore':'A','support':'B','supportive':'B','dominate':'C','dominant':'C',
        '忽略偏好':'A','支持性偏好':'B','主导性偏好':'C'}

def gold_policy(value,count):
    if count==1 and value in LABELS:return LABELS[value]
    if not isinstance(value,str) or len(value)!=count or set(value)-set('ABC'):
        raise ValueError('Unknown evaluation intent encoding')
    return value

def main():
    plan=json.loads((OUT/'PLAN.json').read_text());rows=[];shared={}
    for case in plan['cases']:
        # Private references are accessed only here in the offline evaluation layer.
        candidates=[]
        for p in (RUN/'outcomes').glob('*/*.json'):
            if '.generation.' in p.name:continue
            r=json.loads(p.read_text())
            if r.get('uid')==case['uid'] and r.get('answer_status')=='OK':candidates.append(r)
        if not candidates:continue
        ref=json.loads((ROOT/case['evaluation_path']).read_text())
        for r in candidates:
            selection=r['selection'];pred=selection['aggregation']['policy']
            gold=gold_policy(ref['intent_type'],len(selection['memory_ids']))
            if case['uid'] in shared:assert shared[case['uid']]==selection,'Two generation modes did not share estimates'
            shared[case['uid']]=selection
            rows.append({'uid':case['uid'],'arm':r['arm'],'predicted_intent':pred,'gold_intent':gold,
                         'matched':sum(a==b for a,b in zip(pred,gold)),'total':len(gold),
                         'full_match':pred==gold,'generation_score_status':r['score_status'],
                         'generation_score':r.get('score'), 'memory_ids':selection['memory_ids']})
    unique={r['uid']:r for r in rows}
    result={'rows':rows,'unique_predicted_roots':len(unique),'expected_roots':8,
            'matched':sum(r['matched'] for r in unique.values()),'total':sum(r['total'] for r in unique.values()),
            'note':'Discriminative intent diagnostic only. Do not equate this to final-answer quality or count two generation modes as independent intent predictions.',
            'human_reviews':0,'new_api_requests':0}
    (OUT/'INTENT_DIAGNOSTIC.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['unique_predicted_roots','matched','total']}))
if __name__=='__main__':main()
