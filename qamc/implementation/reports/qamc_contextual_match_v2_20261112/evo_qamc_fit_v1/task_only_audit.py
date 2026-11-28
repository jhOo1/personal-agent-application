"""Check actual inference requests for the history-free task planning condition."""
from collections import Counter
import json

from trial import ACTOR, RUN, sha

OUT=RUN.with_name(RUN.name+'_task_only')


def read(path):
    return json.loads(path.read_text())


def manifest(stage):
    path=OUT/'private'/f'{stage}_MANIFEST.json'
    if not path.exists():
        return {}
    units=read(path)['units']
    result={row['unit']['root_id']:row['request'] for row in units}
    assert len(units)==len(result)
    return result


def receipts(stage):
    result={}
    for p in (OUT/stage/'visible').glob('*/record.json'):
        record=read(p)
        uid=record['unit']['root_id']
        assert uid not in result
        request=read(p.with_name('request.json'))
        assert record['request_sha256']==sha(request) and record['automatic_retries']==0
        result[uid]=(record,request,p)
    return result


def audit():
    base=read(RUN/'private/FROZEN.json')
    cards={r['uid']:r['payload'] for r in base['rows']}
    pin=read(OUT/'private/FROZEN.json')
    plans=manifest('Plan')
    assert plans.keys()==cards.keys()
    for uid,wire in plans.items():
        values=json.loads(wire['messages'][1]['content'])
        assert values=={'task':cards[uid]['task']}
        assert sha(wire)==pin['request_hashes'][uid]
    plan_receipts=receipts('Plan')
    for uid,(_,wire,_) in plan_receipts.items():
        assert plans[uid]==wire
    answers=manifest('Actor')
    for uid,wire in answers.items():
        record,_,path=plan_receipts[uid]
        assert record['status']=='OK'
        reply=read(path.with_name('response.json'))['answer']
        assert wire['messages'][0]['content']==ACTOR
        assert json.loads(wire['messages'][1]['content'])=={**cards[uid],'plan':reply}
    answer_receipts=receipts('Actor')
    for uid,(_,wire,_) in answer_receipts.items():
        assert answers[uid]==wire
    return dict(assigned=len(cards),planning_requests_verified=len(plans),
                plan_receipt_status=Counter(x[0]['status'] for x in plan_receipts.values()),
                actor_requests_verified=len(answers),
                actor_receipt_status=Counter(x[0]['status'] for x in answer_receipts.values()))


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
