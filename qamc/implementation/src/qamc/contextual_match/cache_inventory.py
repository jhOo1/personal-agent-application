"""Targeted, read-only inventory using existing durable ledger schemas.

Unlike the legacy inventory, unrelated judge frames are not read. Selection is
still by exact request digest and lexicographic path, never by a model score.
"""
import json
from pathlib import Path
import sqlite3
from qamc.common import sha


def inventory(root,wanted):
    root=Path(root);wanted=set(wanted);records=[];checked=[];skips=[]
    def portable(path):
        return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    def resolve(value,base):
        if not isinstance(value,str):return None
        path=Path(value)
        return next((p for p in ([path] if path.is_absolute() else [base/path,root/path]) if p.is_file()),None)
    def append(digest,request,response,status,origin):
        if digest not in wanted:return
        valid=False
        if request is not None:
            body=json.loads(request.read_text());valid=sha(body)==digest
        records.append({'body_sha256':digest,'request_path':portable(request) if valid else None,
            'response_path':portable(response) if valid and response is not None else None,
            'status':status if valid else 'PRIOR_METADATA_ONLY_DELIVERY_UNRESOLVED','origin':origin})
    def query(db,sql,field):
        values=sorted(wanted)
        for start in range(0,len(values),400):
            part=values[start:start+400]
            yield from db.execute(sql+' WHERE '+field+' IN ('+','.join('?' for _ in part)+')',part)
    for path in sorted((root/'runs').rglob('samples.sqlite')):
        with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
            columns={r[1] for r in db.execute('PRAGMA table_info(samples)')}
            if not {'unit_key','request_sha','status'}<=columns:skips.append(portable(path));continue
            checked.append(portable(path))
            for key,digest,status in query(db,'SELECT unit_key,request_sha,status FROM samples','request_sha'):
                base=path.parent/'visible'/key
                append(digest,resolve('request.json',base),resolve('response.json',base),
                       'ok' if status=='COMPLETE' else status,portable(path))
    for path in sorted((root/'runs').rglob('ledger.sqlite')):
        with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
            columns={r[1] for r in db.execute('PRAGMA table_info(requests)')}
            if 'data' not in columns:skips.append(portable(path));continue
            checked.append(portable(path))
            for (raw,) in query(db,'SELECT data FROM requests',"json_extract(data,'$.payload_sha')"):
                row=json.loads(raw)
                append(row['payload_sha'],resolve(row.get('request_path'),path.parent),
                       resolve(row.get('response_path'),path.parent),row['status'],portable(path))
            if 'data' in {r[1] for r in db.execute('PRAGMA table_info(cache_imports)')}:
                for (raw,) in query(db,'SELECT data FROM cache_imports',"json_extract(data,'$.payload_sha')"):
                    row=json.loads(raw)
                    if row.get('source_request_path') and row.get('source_response_path'):
                        append(row['payload_sha'],resolve(row['source_request_path'],root),
                               resolve(row['source_response_path'],root),'ok',portable(path)+'/import')
    for path in sorted((root/'runs').rglob('request_ledger.json')):
        if path.with_name('ledger.sqlite').exists():continue
        checked.append(portable(path));rows=json.loads(path.read_text())
        if not isinstance(rows,list):skips.append(portable(path));continue
        for row in rows:
            if row.get('payload_sha') in wanted:
                append(row['payload_sha'],resolve(row.get('request_path'),path.parent),
                       resolve(row.get('response_path'),path.parent),row['status'],portable(path))
    unique={(r['body_sha256'],r['request_path'],r['response_path'],r['status']):r for r in records}
    return {'records':sorted(unique.values(),key=lambda r:(r['request_path'] or '',r['body_sha256'])),
            'checked_journals':checked,'schema_skips':skips,'new_LLM_calls':0,
            'wanted':sorted(wanted),'choice_rule':'exact wire; first lexicographic path; no score access'}
