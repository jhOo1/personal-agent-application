"""New finite-stage ceilings and unchanged durable transport protections."""
import json
from qamc.bace.runtime import BaceGateway
from qamc.b7_api import CallError
from .audit import OUT


class StageGateway(BaceGateway):
    def __init__(self, path, stage, **kwargs):
        limits=json.loads((OUT/'DISPATCH_LIMITS.json').read_text())
        if stage not in limits['cumulative_namespace_request_ceilings']:
            raise ValueError('Stage not authorized by frozen dispatch plan')
        super().__init__(path,request_cap=limits['cumulative_namespace_request_ceilings'][stage],
                         concurrency=8,spacing_seconds=6.1,**kwargs)

    def _complete_attempt(self,key,system,payload,max_tokens=4096):
        with self.lock:
            failures=[json.loads(row[0]) for row in self.db.execute('SELECT data FROM requests')]
            unknown=[r for r in failures if r.get('status') in
                     ('transport_error_delivery_unknown','protocol_error')]
            if len(unknown)>=2:
                (self.root/'STOP').write_text('Two retained unknown/protocol failures; no blind retries.')
                self.disabled=True
        return super()._complete_attempt(key,system,payload,max_tokens)
