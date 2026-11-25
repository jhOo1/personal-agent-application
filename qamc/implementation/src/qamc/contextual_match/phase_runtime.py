"""Shared bounded dispatch for new component phases; no calls on import.

The phase owns its outputs, cache manifests and deferred grades. Parent data
and inference modules stay read-only. Every model block remains sequential.
"""
import json
from pathlib import Path
import time
import os
from qamc.common import sha,canonical,token_estimate
from qamc.transport_helpers import atomic_json
from proposals.qamc_protocol_alignment.transport import NativeSampler
from proposals.qamc_protocol_alignment.sampling import sampling_key,validate_public_request
from proposals.qamc_sentence_units.runtime import Runtime,frozen,read
import proposals.qamc_sentence_units.runtime as runtime_module
from proposals.qamc_pa_transfer.cache_acceleration import prefilter_exact
from .cache_inventory import inventory
from .cache import service_filtered


GPT_STAGES={'RPEvalJudge','PersistJudge'}


def model_block(stage):return 'gpt41' if stage in GPT_STAGES else 'qwen'


class PhaseDispatcher:
    def __init__(self,root,out,run,plan,check,namespace):
        self.root,self.out,self.run=Path(root),Path(out),Path(run)
        self.plan,self.check,self.namespace=plan,check,namespace
        self.allowed=set(plan['allowed_unit_keys'])
        runtime_module.exact=prefilter_exact
        self.runtimes={key:Runtime(self.root,self.out/key,self.run/key,check,sampler_class=self.sampler)
                       for key in ('qwen','gpt41')}

    def cooldown(self):
        until=0.
        for path in (self.root/'runs'/self.namespace).glob('**/execution/visible/*/record.json'):
            record=read(path)
            if record['status'] not in ('OK','PENDING_DELIVERY_UNKNOWN'):
                until=max(until,record.get('started_unix',0)+record.get('elapsed_seconds',0)+300)
        return until

    def sampler(self,*args,**kwargs):
        sampler=NativeSampler(*args,**kwargs)
        with sampler.control.lock:
            sampler.control.db.execute('UPDATE dispatch SET cooldown_until=MAX(cooldown_until,?) WHERE id=1',(self.cooldown(),))
            sampler.control.db.commit()
        return sampler

    def validate_job(self,job):
        unit,body=job['unit'],job['request'];validate_public_request(body)
        if sampling_key(unit) not in self.allowed:raise ValueError('Job is outside frozen component allocation')
        protocol=self.plan['protocols'][model_block(unit['stage'])]
        stage=protocol['stages'][unit['stage']]
        if (unit['protocol_sha256']!=sha(protocol) or body['model']!=protocol['model']
                or body['temperature']!=stage['temperature'] or body['max_tokens']!=stage['max_tokens']):
            raise ValueError('Component job differs from frozen model/decoding settings')

    def grade_batches(self,runtime,name,jobs,index):
        pending=[j for j in jobs if runtime.resolve(j['unit'],j['request'],index) is None]
        physical=lambda:{p.parent.name:read(p) for p in (runtime.run/'execution/visible').glob('*/record.json')}
        previous=physical();latest=max(previous.values(),key=lambda r:r['started_unix'],default=None)
        errors=0;offset=0
        while offset<len(pending):
            size=1 if latest is None or latest['status']!='OK' else 8;block=pending[offset:offset+size]
            batch=name+'_b_'+sha([sampling_key(j['unit']) for j in block])[:20]
            runtime.stage({**self.plan,'protocol':self.plan['protocols']['gpt41']},'components',batch,block,index)
            current=physical();new=[r for key,r in current.items() if key not in previous]
            errors+=sum(r['status']!='OK' for r in new)
            latest=max(current.values(),key=lambda r:r['started_unix'],default=None)
            previous=current;offset+=size
            if (new and all(r['status']!='OK' for r in new)) or errors>=2:break
        deferred=[j for j in pending[offset:] if runtime.output(j['unit']) is None]
        frozen(self.out/'deferred_judging'/(name+'_'+sha(deferred)+'.json'),
            {'jobs':deferred,'status':'UNISSUED','no_failed_request_resends':True})

    def dispatch(self,name,jobs):
        if not jobs:return
        self.check(self.plan)
        for job in jobs:self.validate_job(job)
        for key,runtime in self.runtimes.items():
            chosen=[j for j in jobs if model_block(j['unit']['stage'])==key];eligible=[];blocked=0
            for job in chosen:
                body=canonical(job['request']['messages'])
                if token_estimate(body)>32768 or len(body.encode())>2_000_000:
                    frozen(self.run/key/'outputs'/(sampling_key(job['unit'])+'.json'),
                        {'unit':job['unit'],'request_sha256':sha(job['request']),'status':'CAPACITY_BLOCKED',
                         'origin':'OFFLINE_CAPACITY_GUARD','new_physical_request':False})
                    blocked+=1
                else:eligible.append(job)
            if not eligible:continue
            wanted={sha(j['request']) for j in eligible};path=self.out/key/(name+'_CACHE.json')
            index=read(path) if path.exists() else service_filtered(self.root,inventory(self.root,wanted),wanted,self.plan['service_reference_sha256'])
            if index['schema_skips']:raise ValueError('Unrecognized historical ledger schema')
            frozen(path,index)
            atomic_json(self.out/'RUN_STATE.json',{'phase':'RUNNING','pid':os.getpid(),'stage':name,
                'model_block':key,'eligible_units':len(eligible),'capacity_blocked':blocked,
                'updated_unix':time.time(),'goal_complete':False})
            if key=='gpt41':self.grade_batches(runtime,name,eligible,index)
            else:runtime.stage({**self.plan,'protocol':self.plan['protocols'][key]},'components',name,eligible,index)
