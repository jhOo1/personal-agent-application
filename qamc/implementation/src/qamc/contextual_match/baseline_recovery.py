"""Bounded, proven-complete author JSON retries without unknown-delivery resends.

Used only by a separately frozen external-baseline phase. A successful transport
with invalid author JSON is different from an uncertain transport. Every extra
attempt needs its own sampling unit and persisted authorization. Semantic scores
and reference labels are never consulted.
"""
import json
from pathlib import Path
from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key
from proposals.qamc_sentence_units.runtime import Runtime,frozen,read
from proposals.qamc_pa_transfer.cache_acceleration import prefilter_exact


def completed_record(runtime,saved):
    seen=set()
    while saved:
        key=sampling_key(saved['unit'])
        if key in seen:return None
        seen.add(key)
        path=runtime.run/'execution/visible'/key/'record.json'
        if path.exists():
            record=read(path)
            if (record.get('received_done') is True
                    and record.get('unit')==saved['unit']
                    and record.get('status') in ('OK','KNOWN_LENGTH_FAILURE')
                    and record.get('finish_reason')==('stop' if record.get('status')=='OK' else 'length')
                    and record.get('request_sha256')==saved['request_sha256']):
                response=path.with_name('response.json')
                if record['status']=='OK' and (not response.exists()
                        or read(response).get('answer')!=saved.get('response',{}).get('answer')):
                    return None
                return path,record
            return None
        prior=saved.get('reused_unit')
        saved=runtime.output(prior) if prior else None
    return None


class AuthorRetryRuntime(Runtime):
    """Keep ordinary exact-wire reuse, with narrowly authorized author retries."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.retry_validators={}

    def authorize(self,previous,next_job,validator):
        if next_job['unit']['stage'] not in ('MemInductionRecovery','MemReflectionRecovery'):
            raise ValueError('Only author structured stages have retry permission')
        if next_job['unit']['replicate'] not in (1,2):
            raise ValueError('Author stage is limited to three total attempts')
        if previous:
            prior_unit=previous['unit'];next_unit=next_job['unit'];base=next_unit['stage'].removesuffix('Recovery')
            expected_stage=base if next_unit['replicate']==1 else base+'Recovery'
            if (any(prior_unit[k]!=next_unit[k] for k in ('protocol_sha256','root_id','method'))
                    or prior_unit['stage']!=expected_stage or prior_unit['replicate']!=next_unit['replicate']-1):
                raise ValueError('Author retry changed source/method or skipped an attempt')
        evidence=completed_record(self,previous) if previous else None
        if evidence is None:return None
        path,record=evidence
        original=read(path.with_name('request.json'))
        without_cap=lambda body:{k:v for k,v in body.items() if k!='max_tokens'}
        if without_cap(original)!=without_cap(next_job['request']) or next_job['request']['max_tokens']!=16384:
            raise ValueError('Author retry changed messages/model or recovery cap')
        if record['status']=='OK':
            try:validator(previous['response']['answer'])
            except (ValueError,TypeError,KeyError) as exc:reason={'type':'AUTHOR_JSON_CONTRACT','error_type':type(exc).__name__}
            else:return None
        else:reason={'type':'PROVEN_DONE_LENGTH','error_type':'finish_length'}
        key=sampling_key(next_job['unit'])
        authorization={'unit':next_job['unit'],'request_sha256':sha(next_job['request']),
            'previous_unit':previous['unit'],'previous_request_sha256':previous['request_sha256'],
            'physical_record':str(path),'physical_record_sha256':sha(record),'reason':reason,
            'semantic_scores_consulted':False,'automatic_unknown_delivery_retry':False}
        frozen(self.out/'retry_authorizations'/(key+'.json'),authorization)
        self.retry_validators[key]=validator
        return authorization

    def resolve(self,unit,request,index):
        if unit['stage'] not in ('MemInductionRecovery','MemReflectionRecovery'):
            return super().resolve(unit,request,index)
        key=sampling_key(unit);saved=self.output(unit)
        if saved:
            if saved['request_sha256']!=sha(request):raise ValueError('Saved author retry request drift')
            return saved
        path=self.out/'retry_authorizations'/(key+'.json')
        if not path.exists() or key not in self.retry_validators:
            raise ValueError('Author retry lacks a current validated authorization')
        authorization=read(path)
        record_path=Path(authorization['physical_record'])
        if (authorization['unit']!=unit or authorization['request_sha256']!=sha(request)
                or sha(read(record_path))!=authorization['physical_record_sha256']):
            raise ValueError('Author retry authorization or previous physical record changed')
        # Prefer a valid exact cached response to another physical request.
        # An invalid but proven-complete response may be retried under the
        # author's bounded JSON policy; this is never score-based best-of.
        cached=prefilter_exact(self.root,index,request)
        if cached['state']=='EXACT_SUCCESS':
            try:self.retry_validators[key](cached['response']['answer'])
            except (ValueError,TypeError,KeyError):pass
            else:
                value={'unit':unit,'request_sha256':sha(request),'status':'OK',
                    'origin':'EXACT_HISTORICAL_IMPORT','new_physical_request':False,
                    'response':cached['response'],'cache_lineage':{k:v for k,v in cached.items() if k!='response'}}
                frozen(self.run/'outputs'/(key+'.json'),value);return value
        # A source outside this known-complete set cannot be blindly resent,
        # even when another earlier attempt has a different, known outcome.
        for row in index['records']:
            if row['body_sha256']!=sha(request):continue
            source=Path(row['request_path']) if row.get('request_path') else None
            if source is not None and not source.is_absolute():source=self.root/source
            physical=source.with_name('record.json') if source is not None else None
            known=read(physical) if physical is not None and physical.exists() else {}
            if (known.get('received_done') is not True
                    or known.get('status') not in ('OK','KNOWN_LENGTH_FAILURE')
                    or known.get('finish_reason')!=('stop' if known.get('status')=='OK' else 'length')
                    or known.get('request_sha256')!=sha(request)):
                value={'unit':unit,'request_sha256':sha(request),'status':'PRIOR_ATTEMPT_RETAINED',
                    'origin':'AUTHORIZED_RETRY_BLOCKED_BY_UNCERTAIN_HISTORY','new_physical_request':False,
                    'cache_lineage':{'prior_attempts':[v for v in index['records'] if v['body_sha256']==sha(request)]}}
                frozen(self.run/'outputs'/(key+'.json'),value);return value
        # Runtime.stage still checks the phase allocation; NativeSampler still
        # claims this distinct unit durably before HTTP. Identical wire content
        # is intentional only for these proven-complete author JSON attempts.
        return None
