"""Versioned anchored-span recovery; original namespaces and ledger stay intact."""
import argparse
import json
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor,as_completed
from .audit import ROOT,OUT,digest,write_new
from .prepare import RUN
from .eval import verify
from .runtime import BaceGateway,Steps,runner_lock
from .engine import ScoreEngine
from .span_adapter import SpanGateway
from .span_replay import replay
from qamc.common import sha,canonical
from qamc.transport_helpers import atomic_json

OLD=RUN/'quote_space_v2'
NEW=RUN/'anchored_span_v3'
FREEZE=OUT/'ANCHORED_SPAN_REVISION.json'


def prepare():
    plan=verify()
    if FREEZE.exists():
        record=json.loads(FREEZE.read_text())
        for name,h in record['frozen_files'].items():
            if digest(ROOT/name)!=h:raise ValueError('Anchored-span revision drift')
        return plan,record
    with sqlite3.connect(f'file:{RUN}/api/ledger.sqlite?mode=ro',uri=True) as db:
        requests=[json.loads(r[0]) for r in db.execute('SELECT data FROM requests ORDER BY request_id')]
    if any(r['status']=='pending_delivery_unknown' for r in requests):
        raise ValueError('Original requests must finish before checkpoint reconciliation')
    stop=RUN/'api/STOP';reason=json.loads(stop.read_text())
    if reason.get('reason')!='engineering_dispatch_hold_for_saved_exact_quote_offset_audit':
        raise ValueError('Unrelated service stop must not be cleared by interface recovery')
    with sqlite3.connect(f'file:{OLD}/steps.sqlite?mode=ro',uri=True) as db:
        failed=db.execute('SELECT key,input_hash,status,error FROM steps WHERE status!="OK"').fetchall()
    changes=[];retained=[]
    for key,input_hash,status,error in failed:
        if status=='STARTED':raise ValueError('Unresolved step cannot be reissued')
        # Only the first original response is eligible; never select a nicer repair.
        originals=[r for r in requests if r['key']==key]
        original=originals[0] if originals else None
        restored=replay(original) if original and original['status']=='ok' else None
        if restored and restored['errors']['restored'] is None:
            if restored['step_input_hash']!=input_hash:raise ValueError('Saved step input mismatch')
            changes.append({'key':key,'action':'RESTORE_SAVED_RESPONSE','replay':restored})
        elif error=='DispatchStopped: operator_or_quota_stop_no_dispatch' and not any(r['key']==key or r['key'].startswith(key+'/') for r in requests):
            changes.append({'key':key,'action':'RESUME_NEVER_DISPATCHED'})
        else:retained.append(key)
    if NEW.exists():raise ValueError('Unexpected unfrozen recovery directory')
    NEW.mkdir()
    with sqlite3.connect(f'file:{OLD}/steps.sqlite?mode=ro',uri=True) as src,sqlite3.connect(NEW/'steps.sqlite') as dest:
        src.backup(dest)
        for c in changes:
            if c['action']=='RESTORE_SAVED_RESPONSE':
                dest.execute('UPDATE steps SET status="OK",result=?,error=NULL WHERE key=?',
                             (canonical(c['replay']['restored_object']),c['key']))
            else:dest.execute('DELETE FROM steps WHERE key=?',(c['key'],))
        dest.commit()
    copied=[]
    for case in plan['cases']:
        directory=OLD/'cases'/sha(case['uid'])[:24];path=directory/'result.json'
        if not path.exists():continue
        result=json.loads(path.read_text())
        if result['status']=='OK' or any(k.startswith(case['uid']+'/') for k in retained):
            shutil.copytree(directory,NEW/'cases'/directory.name);copied.append(case['uid'])
    files=['src/qamc/bace/'+f for f in ('span_adapter.py','span_replay.py','span_revision.py')]
    record={'version':'anchored_exact_quote_end_v3','parent_namespace':str(OLD),
            'parent_steps_hash':digest(OLD/'steps.sqlite'),'request_count_at_freeze':len(requests),
            'stop_sha256':digest(stop),'copied_cases':copied,'reconciled_steps':changes,
            'retained_failed_steps':retained,'frozen_files':{p:digest(ROOT/p) for p in files},
            'same_model_prompts_sources_and_scores':True,'same_request_cap':plan['request_cap'],
            'old_results_and_failures_preserved':True,'new_model_calls_by_preparation':0}
    write_new(FREEZE,record)
    return plan,record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','regression','score-pilot'])
    args=parser.parse_args()
    with runner_lock(RUN/'runner.lock'):
        plan,record=prepare()
        if args.phase=='prepare':return
        if not json.loads((OUT/'SCORE_SMOKE_V2_GATE.json').read_text())['passed']:
            raise ValueError('Original recovered smoke gate not passed')
        stop=RUN/'api/STOP'
        if stop.exists():
            if digest(stop)!=record['stop_sha256']:raise ValueError('New stop condition needs separate reconciliation')
            stop.rename(NEW/'ENGINEERING_STOP_ARCHIVE.json')
        base=BaceGateway(RUN/'api',request_cap=plan['request_cap'],concurrency=8,spacing_seconds=6.1)
        engine=ScoreEngine(SpanGateway(base),Steps(NEW/'steps.sqlite'))
        rows=[r for r in plan['cases'] if r['phase']==args.phase]
        def one(case):
            directory=NEW/'cases'/sha(case['uid'])[:24];directory.mkdir(parents=True,exist_ok=True)
            path=directory/'result.json'
            if path.exists():return json.loads(path.read_text())
            if base.disabled or (base.root/'STOP').exists():return {'uid':case['uid'],'status':'NOT_DISPATCHED'}
            result={'uid':case['uid'],'phase':case['phase'],'input_hash':case['bundle_sha256']}
            try:
                scores=engine.score(case['uid'],json.loads((ROOT/case['bundle']).read_text()),case['scopes'],directory)
                result.update(status='OK',uses=len(scores['inventory']),overflow=len(scores['unassessed_overflow']))
            except Exception as exc:
                result.update(status='FAILED',error_type=type(exc).__name__,error=str(exc),semantic_score=None)
                with base.lock:requests=[json.loads(r[0]) for r in base.db.execute('SELECT data FROM requests')]
                unknown=[r for r in requests if r['status'] in {'protocol_error','transport_error_delivery_unknown'} and r.get('usage') is None and r.get('upstream_status')!=429]
                if len(unknown)>=2:
                    (base.root/'STOP').write_text('Two unknown transport failures; no blind retry.\n');base.disabled=True
            atomic_json(path,result);print(json.dumps(result),flush=True);return result
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=[f.result() for f in as_completed([pool.submit(one,r) for r in rows])]
        base.export()
        atomic_json(OUT/(args.phase.upper().replace('-','_')+'_V3_RUN.json'),
                    {'passed':all(r['status']=='OK' for r in results),'phase':args.phase,
                     'namespace':'anchored_span_v3','cases':results,'claims_semantic_gain':False})


if __name__=='__main__':main()
