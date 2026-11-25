"""Read-only source-contract failure evidence; never remap source identities."""
import json
import sqlite3
from .audit import OUT
from .prepare import RUN
from .span_replay import replay
from qamc.transport_helpers import atomic_json


def main():
    root=RUN/'api';namespace=RUN/'anchored_span_v3'
    with sqlite3.connect(f'file:{namespace}/steps.sqlite?mode=ro',uri=True) as db:
        failed=db.execute('SELECT key,error FROM steps WHERE status="FAILED"').fetchall()
    with sqlite3.connect(f'file:{root}/ledger.sqlite?mode=ro',uri=True) as db:
        requests=[json.loads(r[0]) for r in db.execute('SELECT data FROM requests ORDER BY request_id')]
    cases=[]
    for key,error in failed:
        records=[]
        for row in requests:
            if not(row['key']==key or row['key'].startswith(key+'/')):continue
            entry={'request_id':row['request_id'],'key':row['key'],'transport_status':row['status']}
            if row['status']=='ok':
                try:
                    result=replay(row)
                    request=json.loads((root/row['request_path']).read_text())
                    payload=json.loads(request['messages'][-1]['content'])
                    payload=payload.get('original_input',payload)
                    units={u['unit_id']:u['exact_text'] for u in payload['input']['units']}
                    issues=[]
                    def visit(x):
                        if isinstance(x,dict):
                            if {'unit_id','start','end','exact_quote'}<=x.keys():
                                text=units.get(x['unit_id'],'');start=x['start'];end=x['end'];quote=x['exact_quote']
                                if not(0<=start<end<=len(text)) or text[start:end]!=quote:
                                    matches=[uid for uid,value in units.items() if quote and quote in value]
                                    issues.append({'declared_span':x,'declared_unit_text':text,
                                                   'exact_match_units':matches,
                                                   'automatic_source_remapping':False})
                            for v in x.values():visit(v)
                        elif isinstance(x,list):
                            for v in x:visit(v)
                    visit(result['restored_object'])
                    entry.update(errors=result['errors'],mechanical_restorations=result['changes'],
                                 remaining_span_issues=issues,response_sha256=result['response_sha256'])
                except Exception as exc:
                    entry['offline_inspection_error']=type(exc).__name__+': '+str(exc)
            records.append(entry)
        cases.append({'step_key':key,'retained_error':error,'requests':records,
                      'final_task_semantic_score':None})
    atomic_json(OUT/'RETAINED_FAILURE_AUDIT_V3.json',{'namespace':'anchored_span_v3',
                'new_model_calls':0,'human_review':0,'cases':cases,
                'scope':'Source matching diagnostics, not final answer correctness or verified semantic attribution.'})
    print(json.dumps({'failed_steps':len(cases),'new_model_calls':0}))


if __name__=='__main__':main()
