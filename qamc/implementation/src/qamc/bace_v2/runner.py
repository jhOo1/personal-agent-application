"""Finite end-to-end stages; cached outcomes and evaluation failures are retained."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from qamc.common import ROOT, sha
from qamc.transport_helpers import atomic_json
from qamc.bace.audit import digest
from qamc.bace.runtime import Steps, runner_lock
from qamc.bace.prepare import small_bundle
from qamc.preference_policy.profile_engine import ProfileEngine
from .engine import ReviewEngine, prompt
from .evaluation import Evaluator, DurableJudge
from .source_catalog import catalog
from .schema import ORGANIZER_SCHEMA
from .inputs import RUN
from .audit import OUT

ARMS = ('B0', 'B1', 'B2', 'B3', 'M0')


class Experiment:
    def __init__(self, gateway, root):
        self.gateway = gateway; self.root = Path(root)
        self.steps = Steps(self.root/'preparation_steps.sqlite')
        self.engine = ReviewEngine(gateway, root, prompt('actor'))
        self.evaluator = Evaluator(gateway, root)
        # Existing Gate implementation and prompts remain unchanged. The wrapper
        # only adds durable call identities before its existing memoization.
        self.gate = ProfileEngine(DurableJudge(gateway, Steps(self.root/'gate_steps.sqlite')))

    def prepare(self, public):
        if not public['preparation']['acknowledgement_required']:
            return public['bundle']
        history = public['history']
        payload = {'history': history}
        system = 'Respond briefly to the user preference in the supplied conversation. Do not invent preferences.'
        request = {'system': system, 'payload': payload, 'model': self.gateway.model, 'max_tokens': 4096}
        key = 'bace_v2/preparation/ack/'+sha(request)
        answer = self.steps.run(key, request, lambda: self.gateway.complete(key, system, payload, 4096))
        if not isinstance(answer, str) or not answer.strip(): raise ValueError('Empty acknowledgment')
        bundle = small_bundle(public['query'], history + [{'id':'ack0','role':'assistant','content':answer}])
        path = self.root/'prepared'/ (sha(public['uid'])[:24]+'.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(path, {'bundle':bundle,'preparation_request_hash':sha(request),
                           'official_native_chat_transport_parity':False})
        return bundle

    def case(self, public, reference_loader):
        uid = public['uid']; directory = self.root/'outcomes'/sha(uid)[:24]
        directory.mkdir(parents=True, exist_ok=True)
        bundle = self.prepare(public); payload = bundle['payload']
        sources = catalog([u for u in payload['units'] if u['source_id']!='__current__'])
        queries = catalog([u for u in payload['units'] if u['source_id']=='__current__'])
        organized = None; organization_error = None
        # Rotate method order independently of labels. Fallback is generated only
        # when needed and uses the same cached Strong result for every arm.
        offset = int(sha(uid)[:8],16)%len(ARMS)
        arms = ARMS[offset:]+ARMS[:offset]
        results = []
        for arm in arms:
            path = directory/(arm+'.json')
            if path.exists():
                results.append(json.loads(path.read_text())); continue
            row = {'uid':uid,'benchmark':public['benchmark'],'arm':arm,
                   'input_hash':bundle['input_hash'],'pipeline_status':'OK','fallback':False}
            try:
                if arm=='B0': answer = self.engine.actor.strong(uid,payload,sources)
                elif arm=='B1':
                    gate_dir = self.root/'existing_gate'/sha(uid)[:24]
                    gate_dir.mkdir(parents=True,exist_ok=True)
                    scope = self.gate.scope(bundle,gate_dir)
                    out = self.gate.answer(bundle,scope,'S0',[],gate_dir)
                    answer = {'uid':uid,'arm':arm,'answer':out['answer'],'status':'ANSWER_COMPLETE',
                        'actor_request_hash':sha([out['actor_system_hash'],out['actor_input_hash']])}
                else:
                    if organization_error: raise RuntimeError(organization_error)
                    if organized is None:
                        try: organized = self.engine.organize(uid,payload,sources,queries,ORGANIZER_SCHEMA)
                        except Exception as exc:
                            organization_error = type(exc).__name__+': '+str(exc); raise
                    answer = self.engine.review(uid,arm,payload,sources,queries,organized)
            except Exception as exc:
                row.update(pipeline_status='FAILED',error_type=type(exc).__name__,error=str(exc))
                try:
                    answer = {**self.engine.actor.strong(uid,payload,sources),'arm':arm}
                    row['fallback'] = True
                except Exception as fallback_exc:
                    row.update(answer_status='FAILED',score_status='NOT_RUN',
                               fallback_error=type(fallback_exc).__name__+': '+str(fallback_exc))
                    atomic_json(path,row);results.append(row);continue
            # Only this boundary opens the evaluation file. It is never handed to
            # the preparation, Gate, organizer, reviewers or Actor.
            score = self.evaluator.score({'benchmark':public['benchmark'],'query':public['query']},
                                         reference_loader(),answer)
            row.update(answer=answer, evaluation=score, answer_status='ANSWER_COMPLETE',
                       score_status=score['score_status'])
            atomic_json(path,row);results.append(row)
        return results


def load_input(item):
    for field in ('inputs','evaluation_references'):
        if digest(ROOT/item[field]['path']) != item[field]['sha256']:
            raise ValueError('Frozen input/reference drift')
    public = json.loads((ROOT/item['inputs']['path']).read_text())
    return public, lambda: json.loads((ROOT/item['evaluation_references']['path']).read_text())


def report():
    rows = [json.loads(p.read_text()) for p in (RUN/'outcomes').glob('*/*.json')]
    summary = {'completed_cells':len(rows),'answer_complete':sum(r.get('answer_status')=='ANSWER_COMPLETE' for r in rows),
        'valid_scores':sum(r.get('score_status')=='OK' for r in rows),
        'pipeline_failures':sum(r['pipeline_status']=='FAILED' for r in rows),
        'fallback_cells':sum(r['fallback'] for r in rows),'new_model_calls_from_report':0}
    atomic_json(OUT/'RUN_STATUS.json',summary)
    print(json.dumps(summary))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['smoke','dev','report'])
    args=parser.parse_args()
    if args.stage=='report':report();return
    from .freeze import verify
    verify()
    if args.stage=='dev':
        gate=OUT/'SMOKE_ACCEPTANCE.json'
        if not gate.exists() or json.loads(gate.read_text()).get('accepted') is not True:
            raise ValueError('Smoke acceptance required before development dispatch')
    phase='SMOKE' if args.stage=='smoke' else 'OPT'
    items=json.loads((OUT/(phase+'_INPUTS.json')).read_text())
    # A stage is finite by its frozen task manifest. Stage-wide request limits
    # are separately frozen before any real dispatch; old caps are not reused.
    from .transport import StageGateway
    with runner_lock(RUN/'runner.lock'):
        gateway=StageGateway(RUN/'api',stage=args.stage)
        experiment=Experiment(gateway,RUN)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures={pool.submit(experiment.case,*load_input(item)):item['uid'] for item in items}
            for future in as_completed(futures):
                uid=futures[future]
                try:
                    rows=future.result()
                    print(json.dumps({'uid':uid,'cells':len(rows),'valid_scores':sum(r.get('score_status')=='OK' for r in rows)}),flush=True)
                except Exception as exc:
                    atomic_json(RUN/('case_failure_'+sha(uid)[:24]+'.json'),
                                {'uid':uid,'error_type':type(exc).__name__,'error':str(exc)})
                    print(json.dumps({'uid':uid,'case_error':type(exc).__name__}),flush=True)
        report()


if __name__=='__main__':main()
