"""Normalize fixed historical receipts without retrying failed or unknown calls."""
from copy import deepcopy
import json
from pathlib import Path
from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key


def read(path):return json.loads(Path(path).read_text())


def receipt(root,output_path,new_unit,seen=None):
    root,output_path=Path(root).resolve(),Path(output_path).resolve()
    if not output_path.is_relative_to(root):raise ValueError('Receipt escapes project')
    seen=set() if seen is None else set(seen)
    if output_path in seen:raise ValueError('Cyclic saved receipt')
    seen.add(output_path);old=read(output_path);digest=old['request_sha256']
    lineage=deepcopy(old.get('cache_lineage'))
    if not lineage:
        physical=output_path.parent.parent/'execution/visible'/(old.get('sample_key') or sampling_key(old['unit']))
        request=physical/'request.json'
        if not request.exists():
            if old.get('reused_unit'):
                other=output_path.parent/(sampling_key(old['reused_unit'])+'.json')
                value,refs=receipt(root,other,new_unit,seen)
                if value['request_sha256']!=digest:raise ValueError('Alias wire differs')
                if old['status']=='OK' and value.get('response')!=old.get('response'):raise ValueError('Alias answer differs')
                return value,[output_path,*refs]
            raise ValueError('No physical or explicit retained-metadata receipt')
        body,response,record=read(request),read(physical/'response.json'),read(physical/'record.json')
        if sha(body)!=digest or record['request_sha256']!=digest:raise ValueError('Saved request identity differs')
        pointer={'body_sha256':digest,'request_path':str(request.relative_to(root)),
            'response_path':str((physical/'response.json').relative_to(root)),
            'status':record['status'],'origin':str((physical/'record.json').relative_to(root))}
        if old['status']=='OK':
            if record['status']!='OK' or response!=old['response']:raise ValueError('Saved success differs from witness')
            lineage={'state':'EXACT_SUCCESS','chosen':pointer,'score_based_selection':False}
        else:lineage={'state':'PRIOR_ATTEMPT_RETAINED','prior_attempts':[pointer],'new_call_permitted':False,'score_based_selection':False}
    ok=old['status']=='OK'
    if lineage.get('state')!=('EXACT_SUCCESS' if ok else 'PRIOR_ATTEMPT_RETAINED'):
        raise ValueError('Saved status and lineage disagree')
    value={'unit':new_unit,'request_sha256':digest,'new_physical_request':False,
        'origin':'EXACT_HISTORICAL_IMPORT' if ok else 'PRIOR_ATTEMPT_RETAINED',
        'status':'OK' if ok else 'PRIOR_ATTEMPT_RETAINED','cache_lineage':lineage}
    if ok:value['response']=deepcopy(old['response'])
    refs=[output_path]
    pointers=([lineage['chosen']] if 'chosen' in lineage else [])+lineage.get('prior_attempts',[])
    for p in pointers:
        if p['body_sha256']!=digest:raise ValueError('Retained attempt wire differs')
        if p['request_path'] is None:continue
        request=(root/p['request_path']).resolve()
        if not request.is_relative_to(root):raise ValueError('Public witness escapes project')
        refs += [request,request.with_name('response.json'),request.with_name('record.json')]
        if sha(read(request))!=digest:raise ValueError('Referenced public request differs')
        record=read(request.with_name('record.json'))
        if record['request_sha256']!=digest:raise ValueError('Referenced record identity differs')
        if ok and p is lineage.get('chosen'):
            if record['status']!='OK' or read(request.with_name('response.json'))!=old['response']:
                raise ValueError('Cached success differs from chosen physical witness')
    return value,refs
