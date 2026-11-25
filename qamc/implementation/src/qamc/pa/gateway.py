"""Stage-bounded transport; never clears old service stops or retries unknown work."""
import json
from datetime import datetime, timezone
from pathlib import Path
from qamc.bace.runtime import BaceGateway
from qamc.b7_api import CallError
from qamc.common import parse_object, sha, token_estimate, canonical


def validate_service_authorization(auth,stop_path):
    if auth.get('authority')!='direct_user_service_restoration' or not auth.get('user_reply'):
        raise ValueError('New direct service-restoration confirmation required')
    timestamp=datetime.fromisoformat(auth['confirmed_at_utc'].replace('Z','+00:00'))
    if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc):
        raise ValueError('Invalid restoration timestamp')
    if not stop_path.exists() or auth.get('legacy_stop_sha256')!=sha(stop_path.read_bytes()):
        raise ValueError('Restoration must acknowledge the exact retained legacy stop')
    if timestamp.timestamp()<stop_path.stat().st_mtime:
        raise ValueError('Restoration predates the current stop')


class StageGateway(BaceGateway):
    def __init__(self,root,plan,auth,legacy_stop,config=None):
        validate_service_authorization(auth,Path(legacy_stop))
        self.stage=plan
        super().__init__(root,request_cap=plan['request_cap'],config=config,
                         concurrency=plan['concurrency'],spacing_seconds=plan['spacing_seconds'])
        # New stage ledger is isolated. Parent caches/failures are still inspected
        # by the existing transport. No old STOP is removed or ignored by default.
        self.service_recovery={'authority':auth['authority'],'epoch_id':auth['epoch_id'],
                               'confirmed_at_utc':auth['confirmed_at_utc']}
        self.recovery_cutoff=datetime.fromisoformat(auth['confirmed_at_utc'].replace('Z','+00:00')).timestamp()
        self.input_estimate_cap=plan['input_estimate_token_cap']

    def complete(self,key,system,payload,max_tokens=4096):
        if max_tokens>8192:raise ValueError('Unfrozen output cap')
        messages=[{'role':'system','content':system},{'role':'user','content':payload if isinstance(payload,str) else json.dumps(payload,ensure_ascii=False)}]
        body={'model':self.model,'messages':messages,'temperature':0,'max_tokens':max_tokens,
              'stream':True,'stream_options':{'include_usage':True}}
        payload_hash=sha(body)
        if payload_hash in self.external_failures and payload_hash not in self.external_cache:
            raise CallError('historical_failed_payload_not_authorized_for_retry')
        estimate=token_estimate(canonical([system,payload]))
        if estimate>self.input_estimate_cap:
            self.event(key=key,status='input_estimate_gate_no_dispatch',estimate=estimate)
            raise CallError('input_estimate_gate_no_dispatch')
        return super().complete(key,system,payload,max_tokens)

    def _complete_attempt(self,key,system,payload,max_tokens=4096):
        with self.lock:
            failures=[json.loads(r[0]) for r in self.db.execute('SELECT data FROM requests')]
            failures=[r for r in failures if r['status'] in {'protocol_error','transport_error_delivery_unknown'}]
            if len(failures)>=2:
                (self.root/'STOP').write_text('Two retained PA stage transport/protocol failures')
                self.disabled=True
        return super()._complete_attempt(key,system,payload,max_tokens)

    def object(self,key,prompt,payload,validator=None,max_tokens=4096):
        # Deterministic JSON extraction only. Invalid semantic decisions are not
        # regenerated under the label of format repair.
        raw=self.complete(key,prompt,payload,max_tokens)
        try:
            obj=parse_object(raw)
            if validator:validator(obj)
            return obj
        except (ValueError,KeyError,TypeError,AssertionError) as exc:
            self.event(key=key,status='json_contract_failed_no_retry',error=str(exc))
            raise
