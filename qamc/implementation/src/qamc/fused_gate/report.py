"""Read-only final-answer reporting for five arms and three separate benchmarks."""
import json,sqlite3
from collections import Counter
from qamc.pa.report import metrics
from qamc.transport_helpers import atomic_json
ARMS=('G0','R0','S0','V0','F0')

def report(run,out,plan):
    rows=[json.loads(p.read_text()) for p in (run/'outcomes').glob('*/*.json') if p.stem in ARMS]
    summaries=[];paired=[]
    for bench in ('rpeval','benchpres','prefeval'):
        expected=sum(c['benchmark']==bench for c in plan['cases'])
        for arm in ARMS:
            rr=[r for r in rows if r['benchmark']==bench and r['arm']==arm]
            summaries.append({'benchmark':bench,'arm':arm,'expected':expected,'saved':len(rr),'answers':sum(r.get('answer_status')=='OK' for r in rr),'fallbacks':sum(r.get('fallback',False) for r in rr),'system_metrics':metrics(bench,rr),'normal_metrics':metrics(bench,[r for r in rr if r['pipeline_status']=='OK'])})
        for a,b in [('F0','G0'),('F0','S0'),('F0','V0'),('F0','R0'),('V0','G0')]:
            for cohort in ('normal','system'):
                aa={r['uid']:r for r in rows if r['benchmark']==bench and r['arm']==a and r.get('score_status')=='OK' and (cohort=='system' or r['pipeline_status']=='OK')}
                bb={r['uid']:r for r in rows if r['benchmark']==bench and r['arm']==b and r.get('score_status')=='OK' and (cohort=='system' or r['pipeline_status']=='OK')}
                ids=sorted(aa.keys()&bb.keys())
                paired.append({'benchmark':bench,'candidate':a,'baseline':b,'cohort':cohort,'common_valid':len(ids),'uids':ids,'candidate_metrics':metrics(bench,[aa[i] for i in ids]),'baseline_metrics':metrics(bench,[bb[i] for i in ids])})
    calls=[];cache=0;db=run/'api/ledger.sqlite'
    if db.exists():
        with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as c:
            calls=[json.loads(x[0]) for x in c.execute('select data from requests')]
            cache=c.execute('select count(*) from cache_imports').fetchone()[0]
    ledger={'physical_requests':len(calls),'status_counts':dict(Counter(r['status'] for r in calls)),'usage':{k:sum((r.get('usage') or {}).get(k,0) or 0 for r in calls) for k in ('prompt_tokens','completion_tokens','total_tokens')},'unknown_usage':sum(r.get('usage') is None for r in calls),'cache_imports':cache,'user_request_count_ceiling':None,'finite_task_attempt_guard':plan['request_cap']}
    result={'expected_cells':len(plan['cases'])*len(ARMS),'saved_cells':len(rows),'status':'COMPLETE_REQUIRES_REVIEW' if len(rows)==len(plan['cases'])*len(ARMS) else ('STOPPED' if (run/'api/STOP').exists() else 'PARTIAL'),'summaries':summaries,'paired':paired,'ledger':ledger,'human_reviews':0,'new_calls_from_report':0}
    out.mkdir(parents=True,exist_ok=True);atomic_json(out/'RESULTS.json',result);atomic_json(out/'CALL_LEDGER_SUMMARY.json',ledger)
    atomic_json(out/'RETAINED_FAILURES.json',[r for r in rows if r['pipeline_status']!='OK' or r.get('score_status')=='FAILED'])
    lines=['# FusedGate saved results','','Development only. Shared Actor; adapted automatic Qwen scoring; no SOTA claim. V0 denotes frozen binary v2; F0 is the one-call Gate. Failures are not semantic zeros.','',f"Saved {len(rows)}/{result['expected_cells']}; {result['status']}.",'','| Benchmark | Arm | Valid/expected | Fallback | Metrics |','|---|---|---:|---:|---|']
    for r in summaries:lines.append(f"| {r['benchmark']} | {r['arm']} | {r['system_metrics']['valid']}/{r['expected']} | {r['fallbacks']} | {json.dumps(r['system_metrics'])} |")
    lines+=['','Cost is supplementary; the research objective is quality and protocol-comparable SOTA, not request minimization.','',json.dumps(ledger,indent=2)]
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n');return result
