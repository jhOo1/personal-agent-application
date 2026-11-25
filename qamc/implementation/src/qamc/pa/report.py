"""Read-only saved-answer analysis; never dispatches or backfills a Judge."""
import json
import sqlite3
from collections import Counter
from pathlib import Path
from qamc.transport_helpers import atomic_json

ARMS=('R0','G0','S0','V0','V1','V2','V2_NO_LEVEL')


def metrics(benchmark,rows):
    scores=[r['score'] for r in rows if r.get('score_status')=='OK']
    n=len(scores)
    if not n:return {'valid':0}
    if benchmark=='benchpres':
        mn=sum(s['mr_numerator'] for s in scores);md=sum(s['mr_denominator'] for s in scores)
        an=sum(s['aar_numerator'] for s in scores);ad=sum(s['aar_denominator'] for s in scores)
        return {'valid':n,'MR':mn/md if md else None,'MR_count':[mn,md],
                'AAR':an/ad if ad else None,'AAR_count':[an,ad],
                'completeness':sum(s['task_completeness'] for s in scores)/n}
    if benchmark=='prefeval':return {'valid':n,'adherence':sum(s['preference_adherence_accuracy'] for s in scores)/n}
    return {'valid':n,'atomic_match':sum(s['matched'] for s in scores)/sum(s['total'] for s in scores),
            'query_full_match':sum(s['matched']==s['total'] for s in scores)/n,
            **{key:sum(s['severity'][key] for s in scores)/n for key in ('OPB','UPB','RII','FM','VG','Judge')}}


def build_report(run,output,plan):
    rows=[]
    for path in (run/'outcomes').glob('*/*.json'):
        if path.stem in ARMS:rows.append(json.loads(path.read_text()))
    summaries=[];pairs=[]
    for bench in ('benchpres','rpeval','prefeval'):
        expected=sum(item['benchmark']==bench for item in plan['cases'])
        for arm in ARMS:
            subset=[r for r in rows if r['benchmark']==bench and r['arm']==arm]
            summaries.append({'benchmark':bench,'arm':arm,'expected':expected,'saved':len(subset),
                              'answers':sum(r.get('answer_status')=='OK' for r in subset),
                              'fallback':sum(r.get('fallback',False) for r in subset),
                              'pipeline_failures':sum(r['pipeline_status']!='OK' for r in subset),
                              'system_metrics':metrics(bench,subset),
                              'normal_metrics':metrics(bench,[r for r in subset if r['pipeline_status']=='OK'])})
        for cohort in ('system','normal'):
            for candidate,baseline in [('V0','G0'),('V1','G0'),('V2','G0'),('V2','S0'),('V2','V0'),('V1','V0'),('V2','V2_NO_LEVEL')]:
                a={r['uid']:r for r in rows if r['benchmark']==bench and r['arm']==candidate and r.get('score_status')=='OK' and (cohort=='system' or r['pipeline_status']=='OK')}
                b={r['uid']:r for r in rows if r['benchmark']==bench and r['arm']==baseline and r.get('score_status')=='OK' and (cohort=='system' or r['pipeline_status']=='OK')}
                ids=sorted(a.keys()&b.keys())
                am=metrics(bench,[a[i] for i in ids]);bm=metrics(bench,[b[i] for i in ids])
                delta={k:am[k]-bm[k] for k in am.keys()&bm.keys() if k!='valid' and isinstance(am[k],(int,float)) and isinstance(bm[k],(int,float))}
                pairs.append({'benchmark':bench,'candidate':candidate,'baseline':baseline,'cohort':cohort,
                              'common_valid':len(ids),'uids':ids,'candidate_metrics':am,'baseline_metrics':bm,'delta':delta})
    calls=[];cache=0;db=run/'api/ledger.sqlite'
    if db.exists():
        with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as connection:
            calls=[json.loads(r[0]) for r in connection.execute('SELECT data FROM requests')]
            cache=connection.execute('SELECT count(*) FROM cache_imports').fetchone()[0]
    token_fields=('prompt_tokens','completion_tokens','total_tokens')
    usage={k:sum((r.get('usage') or {}).get(k,0) or 0 for r in calls) for k in token_fields}
    ledger={'physical_requests':len(calls),'statuses':dict(Counter(r['status'] for r in calls)),
            'usage':usage,'unknown_usage':sum(r.get('usage') is None for r in calls),'imported_cache_entries':cache,
            'reasoning_not_added_again_to_completion':True,'remaining_stage_requests':plan['request_cap']-len(calls)}
    result={'status':'NOT_RUN' if not rows else 'PARTIAL_OR_COMPLETE_REQUIRES_GATE_AUDIT',
            'expected_cells':len(plan['cases'])*len(ARMS),'saved_cells':len(rows),
            'summaries':summaries,'paired':pairs,'ledger':ledger,'human_reviews':0,'new_calls_by_report':0}
    output.mkdir(parents=True,exist_ok=True);atomic_json(output/'RESULTS.json',result)
    atomic_json(output/'CALL_LEDGER_SUMMARY.json',ledger)
    text=['# QAMC-PA saved results','',f"Status: {result['status']}. Saved {len(rows)}/{result['expected_cells']} cells.",
          'Development/regression data only. Qwen scoring variants; failures are not semantic zeros. Human reviews: 0.',
          '', '| Benchmark | Arm | Valid / expected | Fallback | Metrics |','|---|---|---:|---:|---|']
    for row in summaries:text.append(f"| {row['benchmark']} | {row['arm']} | {row['system_metrics']['valid']}/{row['expected']} | {row['fallback']} | {json.dumps(row['system_metrics'])} |")
    text+=['','## Ledger','',json.dumps(ledger,indent=2),'','No SOTA or improvement conclusion without complete paired outcomes and gate review.']
    (output/'RESULTS.md').write_text('\n'.join(text)+'\n')
    return result
