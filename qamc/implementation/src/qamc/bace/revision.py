"""Offline-certified Unicode-space repair; same prompts, inputs and API ledger."""
import argparse
import json
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor,as_completed
from .audit import ROOT,OUT,digest,write_new
from .prepare import RUN
from .eval import verify
from .runtime import BaceGateway,Steps,runner_lock
from .quote_adapter import QuoteGateway
from .engine import ScoreEngine
from qamc.common import sha
from qamc.transport_helpers import atomic_json

V2=RUN/'quote_space_v2'


def prepare():
    plan=verify();V2.mkdir(exist_ok=True)
    replay=json.loads((OUT/'UNICODE_SPACE_REPLAY.json').read_text())
    if len(replay)!=2 or not all(r['passed'] and len(r['changes'])==1 for r in replay):
        raise ValueError('Saved response replay is incomplete')
    frozen=OUT/'QUOTE_SPACE_REVISION.json'
    files=[ROOT/'src/qamc/bace/quote_adapter.py',ROOT/'src/qamc/bace/revision.py']
    if frozen.exists():
        data=json.loads(frozen.read_text())
        for name,h in data['frozen_files'].items():
            if digest(ROOT/name)!=h:raise ValueError('Revision code drift')
        return plan
    db_path=V2/'steps.sqlite'
    if db_path.exists():raise ValueError('Unexpected unregistered revision checkpoint')
    with sqlite3.connect(f'file:{RUN}/steps.sqlite?mode=ro',uri=True) as source,sqlite3.connect(db_path) as dest:
        source.backup(dest)
        failed=dest.execute('SELECT key,status,error FROM steps WHERE status != "OK"').fetchall()
        expected='benchpres/0883cf86601639800d50/proposal/deny'
        if failed!=[(expected,'FAILED','ValueError: Quote differs from original source')]:
            raise ValueError('Only the exact offline-replayed Unicode failure may reconcile')
        dest.execute('DELETE FROM steps WHERE key=?',(expected,));dest.commit()
    copied=[]
    for case in plan['cases']:
        old=RUN/'cases'/sha(case['uid'])[:24];result=old/'result.json'
        if result.exists() and json.loads(result.read_text())['status']=='OK':
            shutil.copytree(old,V2/'cases'/old.name);copied.append(case['uid'])
    write_new(frozen,{'version':'unicode_Zs_source_copy_v2','old_namespace_preserved':True,
       'old_steps_sha256':digest(RUN/'steps.sqlite'),'reconciled_step':expected,
       'successful_cases_copied':copied,'replay_sha256':digest(OUT/'UNICODE_SPACE_REPLAY.json'),
       'frozen_files':{str(p.relative_to(ROOT)):digest(p) for p in files},
       'same_model_prompts_sources_and_scores':True,'same_api_ledger':str((RUN/'api/ledger.sqlite').relative_to(ROOT)),
       'same_total_cap':plan['request_cap'],'recovery':'first saved proposal reused from exact cache after source-space restoration; no source/proposal resampling'})
    return plan


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','smoke','regression','score-pilot'])
    args=parser.parse_args()
    with runner_lock(RUN/'runner.lock'):
        plan=prepare()
        if args.phase=='prepare':return
        if args.phase!='smoke':
            if not json.loads((OUT/'SCORE_SMOKE_V2_GATE.json').read_text())['passed']:
                raise ValueError('Reconciled smoke not passed')
        rows=plan['cases']
        if args.phase=='smoke':rows=[next(r for r in rows if r['uid'].startswith(b+'/')) for b in ('benchpres','personamem')]
        else:rows=[r for r in rows if r['phase']==args.phase]
        base=BaceGateway(RUN/'api',request_cap=plan['request_cap'],concurrency=8,spacing_seconds=6.1)
        engine=ScoreEngine(QuoteGateway(base),Steps(V2/'steps.sqlite'))
        def one(case):
            directory=V2/'cases'/sha(case['uid'])[:24];directory.mkdir(parents=True,exist_ok=True)
            path=directory/'result.json'
            if path.exists():return json.loads(path.read_text())
            if base.disabled or (base.root/'STOP').exists():return {'uid':case['uid'],'status':'NOT_DISPATCHED'}
            result={'uid':case['uid'],'phase':case['phase'],'input_hash':case['bundle_sha256']}
            try:
                out=engine.score(case['uid'],json.loads((ROOT/case['bundle']).read_text()),case['scopes'],directory)
                result.update(status='OK',uses=len(out['inventory']),overflow=len(out['unassessed_overflow']))
            except Exception as exc:
                result.update(status='FAILED',error_type=type(exc).__name__,error=str(exc),semantic_score=None)
                with base.lock:
                    requests=[json.loads(r[0]) for r in base.db.execute('SELECT data FROM requests')]
                unknown=[r for r in requests if r['status'] in {'protocol_error','transport_error_delivery_unknown'} and r.get('usage') is None and r.get('upstream_status')!=429]
                if len(unknown)>=2:
                    (base.root/'STOP').write_text('Two unknown transport failures; no blind retry.\n');base.disabled=True
            atomic_json(path,result);print(json.dumps(result),flush=True);return result
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=[f.result() for f in as_completed([pool.submit(one,r) for r in rows])]
        base.export()
        atomic_json(OUT/('SCORE_SMOKE_V2_GATE.json' if args.phase=='smoke' else args.phase.upper().replace('-','_')+'_RUN.json'),
                    {'passed':all(r['status']=='OK' for r in results),'phase':args.phase,'cases':results,
                     'claims_semantic_gain':False,'api_ledger':str(base.root/'ledger.sqlite')})


if __name__=='__main__':main()
