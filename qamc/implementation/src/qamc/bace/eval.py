"""Finite score-pilot entry point; reporting is always zero model requests."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from .audit import ROOT,OUT,digest
from .prepare import RUN
from .runtime import BaceGateway,Steps,runner_lock
from .engine import ScoreEngine
from qamc.common import sha
from qamc.transport_helpers import atomic_json


def verify():
    plan=json.loads((OUT/'SCORE_PILOT_PLAN.json').read_text())
    gate=json.loads((OUT/'PHASE0_GATE.json').read_text())
    if not gate['passed']:raise ValueError('Phase 0 not passed')
    for path,h in plan['frozen_files'].items():
        if digest(ROOT/path)!=h:raise ValueError('Frozen implementation drift: '+path)
    for row in plan['cases']:
        if digest(ROOT/row['bundle'])!=row['bundle_sha256']:raise ValueError('Frozen input drift')
        if row.get('scope_source') and digest(ROOT/row['scope_source'])!=row['scope_sha256']:raise ValueError('Scope drift')
    return plan


def report():
    import sqlite3
    from collections import Counter
    plan=json.loads((OUT/'SCORE_PILOT_PLAN.json').read_text())
    results=[]
    for row in plan['cases']:
        path=RUN/'cases'/sha(row['uid'])[:24]/'result.json'
        results.append(json.loads(path.read_text()) if path.exists() else {'uid':row['uid'],'phase':row['phase'],'status':'NOT_DISPATCHED'})
    ledger=RUN/'api/ledger.sqlite';requests=[]
    if ledger.exists():
        with sqlite3.connect(f'file:{ledger}?mode=ro',uri=True) as db:
            requests=[json.loads(r[0]) for r in db.execute('SELECT data FROM requests ORDER BY request_id')]
    usage=[r['usage'] for r in requests if isinstance(r.get('usage'),dict)]
    accounting={'requests':len(requests),'statuses':dict(Counter(r.get('status') for r in requests)),
      'known_usage_requests':len(usage),'unknown_usage_requests':len(requests)-len(usage),
      'prompt_tokens':sum(u.get('prompt_tokens',0) for u in usage),
      'completion_tokens':sum(u.get('completion_tokens',0) for u in usage),
      'total_tokens':sum(u.get('total_tokens',0) for u in usage),'cap':plan['request_cap'],
      'failure_is_semantic_zero':False}
    atomic_json(OUT/'PILOT_PROGRESS.json',{'cases':results,'accounting':accounting})
    print(json.dumps({'case_status':dict(Counter(r['status'] for r in results)),**accounting}),flush=True)


def run(phase):
    plan=verify()
    if phase=='score-pilot':
        smoke=json.loads((OUT/'SCORE_SMOKE_GATE.json').read_text())
        if not smoke['passed']:raise ValueError('Score smoke not passed')
    rows=plan['cases']
    if phase=='smoke':
        rows=[next(r for r in rows if r['uid'].startswith(b+'/')) for b in ('benchpres','personamem')]
    elif phase=='regression':rows=[r for r in rows if r['phase']=='regression']
    elif phase=='score-pilot':rows=[r for r in rows if r['phase']=='score-pilot']
    g=BaceGateway(RUN/'api',request_cap=plan['request_cap'],concurrency=plan['concurrency'],spacing_seconds=plan['spacing_seconds'])
    steps=Steps(RUN/'steps.sqlite');engine=ScoreEngine(g,steps)
    def one(row):
        directory=RUN/'cases'/sha(row['uid'])[:24];directory.mkdir(parents=True,exist_ok=True)
        result_path=directory/'result.json'
        if result_path.exists():return json.loads(result_path.read_text())
        if g.disabled or (g.root/'STOP').exists():return {'uid':row['uid'],'status':'NOT_DISPATCHED'}
        result={'uid':row['uid'],'phase':row['phase'],'input_hash':row['bundle_sha256']}
        try:
            bundle=json.loads((ROOT/row['bundle']).read_text())
            out=engine.score(row['uid'],bundle,row['scopes'],directory)
            result.update(status='OK',uses=len(out['inventory']),overflow=len(out['unassessed_overflow']))
        except Exception as exc:
            result.update(status='FAILED',error_type=type(exc).__name__,error=str(exc),semantic_score=None)
            with g.lock:
                failures=[json.loads(r[0]) for r in g.db.execute('SELECT data FROM requests')]
            unknown=[r for r in failures if r.get('status') in {'protocol_error','transport_error_delivery_unknown'} and r.get('usage') is None and r.get('upstream_status')!=429]
            if len(unknown)>=2:
                (g.root/'STOP').write_text('Two unknown transport failures; explicit recovery review required.\n');g.disabled=True
        atomic_json(result_path,result)
        print(json.dumps(result),flush=True)
        return result
    with runner_lock(RUN/'runner.lock'):
        with ThreadPoolExecutor(max_workers=plan['case_workers']) as pool:
            completed=[f.result() for f in as_completed([pool.submit(one,row) for row in rows])]
        g.export()
        if phase=='smoke':atomic_json(OUT/'SCORE_SMOKE_GATE.json',{'passed':all(r['status']=='OK' for r in completed),'cases':completed,'semantic_gain_claimed':False})
    report()


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['smoke','regression','score-pilot','report'])
    p.add_argument('--use-existing-cache',action='store_true');p.add_argument('--split',choices=['dev','cal'])
    p.add_argument('--new-namespace',action='store_true');args=p.parse_args()
    if args.phase=='report':report()
    else:run(args.phase)


if __name__=='__main__':main()
