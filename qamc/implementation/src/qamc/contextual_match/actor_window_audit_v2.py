"""Read-only public witness resolution, including exact-wire aliases."""
import json
from pathlib import Path

from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key

REQUEST_FIELDS={'model','messages','temperature','max_tokens','stream','stream_options'}
RESPONSE_FIELDS={'answer','model','usage','id','finish_reason'}
RECORD_FIELDS={'status','usage','started_unix','elapsed_seconds','received_done',
               'finish_reason','http_status','error'}


class SavedRuntime:
    """Expose only the saved output interface required for offline replay."""
    def __init__(self,run):self.run=Path(run)

    def output(self,unit):
        path=self.run/'outputs'/(sampling_key(unit)+'.json')
        if not path.exists():return None
        value=json.loads(path.read_text())
        if value['unit']!=unit:raise ValueError('Saved output sampling unit differs')
        return value


def public_trace(root,rt,job):
    """Follow stored lineage; never infer delivery or construct a new client."""
    root=Path(root).resolve();request=job['request'];expected=sha(request)
    if set(request)-REQUEST_FIELDS:raise ValueError('Unexpected public request fields')
    saved=rt.output(job['unit'])
    trace={'unit':job['unit'],'request':request,'request_sha256':expected,
           'status':saved['status'] if saved else 'UNISSUED','physical_request_path':'UNKNOWN'}
    if saved is None:return trace
    trace['origin']=saved.get('origin','UNKNOWN')
    trace['visible_response']={k:v for k,v in saved.get('response',{}).items() if k in RESPONSE_FIELDS}
    def resolve(value,seen):
        key=sampling_key(value['unit'])
        if key in seen:raise ValueError('Cyclic public witness lineage')
        if value['request_sha256']!=expected:raise ValueError('Public witness request changed')
        chosen=value.get('cache_lineage',{}).get('chosen',{})
        path=(root/chosen['request_path']).resolve() if chosen.get('request_path') else (
            rt.run/'execution/visible'/value.get('sample_key',key)/'request.json').resolve()
        if not path.is_relative_to(root):raise ValueError('Witness outside repository')
        if path.exists():return path
        if value.get('reused_unit'):
            prior=rt.output(value['reused_unit'])
            if prior is not None:return resolve(prior,seen|{key})
        return None
    path=resolve(saved,set())
    if path is None:return trace
    if json.loads(path.read_text())!=request:raise ValueError('Physical public request differs')
    record=json.loads(path.with_name('record.json').read_text())
    if record['request_sha256']!=expected:raise ValueError('Physical record request differs')
    if record['status']=='PENDING_DELIVERY_UNKNOWN':raise ValueError('Terminal output has pending witness')
    if saved['status']=='OK':
        response=json.loads(path.with_name('response.json').read_text())
        if record['status']!='OK' or response!=saved['response']:
            raise ValueError('Alias answer differs from public physical response')
    trace.update(physical_request_path=str(path.relative_to(root)),
                 physical_record={k:v for k,v in record.items() if k in RECORD_FIELDS})
    return trace
