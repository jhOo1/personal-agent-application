"""Replay public saved responses against unchanged strict contracts, offline."""
import json
import sqlite3
from .audit import OUT,digest
from .prepare import RUN
from .span_adapter import restore_anchored_ends
from .schemas import validate_inventory,validate_assessments
from qamc.common import parse_object,sha
from qamc.transport_helpers import atomic_json


def replay(row):
    root=RUN/'api'
    request=json.loads((root/row['request_path']).read_text())
    payload=json.loads(request['messages'][-1]['content'])
    if 'original_input' in payload:payload=payload['original_input']
    raw=parse_object(json.loads((root/row['response_path']).read_text())['answer'])
    units={u['unit_id']:u for u in payload['input']['units']}
    fixed,changes=restore_anchored_ends(raw,units)
    errors={}
    for version,obj in [('original',raw),('restored',fixed)]:
        try:
            if '/proposal/' in row['key']:validate_inventory(obj,payload['input'],payload['scopes'])
            else:
                role='allow' if '/allow' in row['key'] else 'deny'
                validate_assessments(obj,role,payload['input'],payload['scopes'],payload['use_inventory'])
            errors[version]=None
        except (ValueError,KeyError,TypeError,AssertionError) as exc:
            errors[version]=type(exc).__name__+': '+str(exc)
    return {'request_id':row['request_id'],'key':row['key'],
            'response_sha256':digest(root/row['response_path']),
            'step_input_hash':sha({'prompt':request['messages'][0]['content'],'request':payload}),
            'errors':errors,'changes':changes,'restored_object':fixed}


def main():
    with sqlite3.connect(f'file:{RUN}/api/ledger.sqlite?mode=ro',uri=True) as db:
        rows=[json.loads(r[0]) for r in db.execute('SELECT data FROM requests ORDER BY request_id')]
    items=[replay(r) for r in rows if r['status']=='ok']
    atomic_json(OUT/'ANCHORED_END_REPLAY.json',{'new_model_calls':0,'original_responses_unchanged':True,
                'pending_requests':sum(r['status']=='pending_delivery_unknown' for r in rows),'items':items})
    print(json.dumps({'replayed':len(items),'restored_valid':sum(x['errors']['restored'] is None for x in items)}))


if __name__=='__main__':main()
