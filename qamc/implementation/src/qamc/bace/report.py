"""Live-safe read-only accounting; incomplete work is not undispatched or wrong."""
import argparse
import json
import sqlite3
from collections import Counter
from .audit import OUT
from .prepare import RUN
from qamc.common import sha
from qamc.transport_helpers import atomic_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--namespace',choices=['original','quote_space_v2','anchored_span_v3'],default='original')
    args=parser.parse_args()
    # Select one declared execution lineage; never choose the best case across runs.
    case_root=RUN if args.namespace=='original' else RUN/args.namespace
    plan=json.loads((OUT/'SCORE_PILOT_PLAN.json').read_text());rows=[];requests=[];steps=[]
    step_path=case_root/'steps.sqlite'
    if step_path.exists():
        with sqlite3.connect(f'file:{step_path}?mode=ro',uri=True) as db:
            steps=list(db.execute('SELECT key,status FROM steps'))
    for case in plan['cases']:
        path=case_root/'cases'/sha(case['uid'])[:24]/'result.json'
        if path.exists():row=json.loads(path.read_text())
        else:
            related=[s for k,s in steps if k.startswith(case['uid']+'/')]
            row={'uid':case['uid'],'phase':case['phase'],
                 'status':'STARTED_NOT_TERMINAL' if related else 'NOT_DISPATCHED',
                 'step_statuses':dict(Counter(related))}
        rows.append(row)
    api=RUN/'api/ledger.sqlite'
    if api.exists():
        with sqlite3.connect(f'file:{api}?mode=ro',uri=True) as db:
            requests=[json.loads(r[0]) for r in db.execute('SELECT data FROM requests ORDER BY request_id')]
    pending=[r for r in requests if r['status']=='pending_delivery_unknown']
    terminal=[r for r in requests if r['status']!='pending_delivery_unknown']
    usage=[r['usage'] for r in requests if isinstance(r.get('usage'),dict)]
    cost={'requests':len(requests),'pending_requests':len(pending),
          'terminal_statuses':dict(Counter(r['status'] for r in terminal)),
          'known_usage_requests':len(usage),'terminal_unknown_usage':sum(r.get('usage') is None for r in terminal),
          'input_tokens':sum(u.get('prompt_tokens',0) for u in usage),
          'output_tokens':sum(u.get('completion_tokens',0) for u in usage),
          'total_tokens':sum(u.get('total_tokens',0) for u in usage),
          'request_cap':plan['request_cap'],'cache_is_independent_generation':False}
    name={'original':'LIVE_PROGRESS.json','quote_space_v2':'LIVE_PROGRESS_V2.json','anchored_span_v3':'LIVE_PROGRESS_V3.json'}[args.namespace]
    atomic_json(OUT/name,{'namespace':args.namespace,'cases':rows,'accounting':cost,
         'file_state_does_not_prove_process_liveness':True,'report_new_requests':0})
    print(json.dumps({'cases':dict(Counter(r['status'] for r in rows)),**cost}),flush=True)


if __name__=='__main__':main()
