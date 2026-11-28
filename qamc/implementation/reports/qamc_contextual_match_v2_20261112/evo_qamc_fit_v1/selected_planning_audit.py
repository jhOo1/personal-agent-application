"""Verify shared planning and Actor instructions in all four actual fit cells."""
from collections import Counter
import json

from selected_planning import OUT, SELECTED, read
from trial import ACTOR, COMMON, POLICIES, RUN, sha


def manifest(path):
    result={}
    for u in read(path)['units']:
        key=u['unit']['root_id'],u['unit']['method']
        assert key not in result
        result[key]=u['request']
    return result


def payload(wire):
    return json.loads(wire['messages'][1]['content'])


def verify():
    original=read(RUN/'private/FROZEN.json')
    rows={r['uid']:r for r in original['rows']}
    spec=read(OUT/'private/FROZEN.json')
    selected={u['unit']['root_id']:payload(u['request']) for u in read(SELECTED/'private/Actor_MANIFEST.json')['units']}
    old=manifest(RUN/'Plan_MANIFEST.json')
    new=manifest(OUT/'Plan_MANIFEST.json')
    spec_rows={r['uid']:r for r in spec['rows']}
    assert set(new)=={(uid,name) for uid in spec_rows for name in POLICIES}
    for (uid,name),wire in new.items():
        archived=old[uid,name]
        assert wire['messages'][0]==archived['messages'][0]
        assert wire['messages'][0]['content']==COMMON+'\n\n'+POLICIES[name]
        assert dict(wire,messages=archived['messages'])==archived
        assert payload(archived)==rows[uid]['payload']
        assert payload(wire)==selected[uid]==spec_rows[uid]['payload']
        assert sha(wire)==spec_rows[uid]['plan_request_hashes'][name]
        assert payload(wire)['task']==payload(archived)['task']
    for card in spec['exact']:
        uid=card['uid']
        assert selected[uid]==rows[uid]['payload']
    assert len(spec_rows)+len(spec['exact'])+len(spec['absent'])==len(rows)

    plan_stats=Counter()
    plan_outputs={}
    for f in (OUT/'Plan/visible').glob('*/record.json'):
        rec=read(f)
        key=rec['unit']['root_id'],rec['unit']['method']
        wire=read(f.with_name('request.json'))
        assert new[key]==wire and rec['request_sha256']==sha(wire) and rec['automatic_retries']==0
        plan_stats[rec['status']]+=1
        if rec['status']=='OK':
            plan_outputs[key]=read(f.with_name('response.json'))['answer']
    actor_path=OUT/'Actor_MANIFEST.json'
    actors=manifest(actor_path) if actor_path.exists() else {}
    for key,wire in actors.items():
        uid,_=key
        assert wire['messages'][0]['content']==ACTOR
        assert payload(wire)==dict(selected[uid],plan=plan_outputs[key])
    return dict(assigned_tasks=len(rows),filtered_tasks=len(spec_rows),exact_task_reuse=len(spec['exact']),
                missing_selected=len(spec['absent']),verified_plan_requests=len(new),
                plan_receipts=plan_stats,verified_actor_requests=len(actors))


if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
