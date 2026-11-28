"""Verify paired final-generation payload provenance for the task-plan crossover."""
from collections import Counter
import json

from crossover import OUT, TASK, SELECTED, RUN, read, sha


def manifest(run):
    doc=read(run/'private/Actor_MANIFEST.json')
    indexed={r['unit']['root_id']:r['request'] for r in doc['units']}
    assert len(indexed)==len(doc['units'])
    return indexed


def audit():
    cards={r['uid']:r for r in read(RUN/'private/FROZEN.json')['rows']}
    pin=read(OUT/'private/FROZEN.json')
    parent, selected, child=(manifest(run) for run in (TASK,SELECTED,OUT))
    counts=Counter()
    exposure={}
    for uid in cards:
        if uid not in parent or uid not in selected:
            counts['parent_unavailable']+=1
            assert uid not in child
            continue
        expected=parent[uid]
        original=json.loads(expected['messages'][1]['content'])
        inherited=json.loads(selected[uid]['messages'][1]['content'])
        exposed=inherited['source_evidence']
        assert len({r['memory_id'] for r in exposed})==len(exposed)
        assert inherited['task']==original['task']==cards[uid]['payload']['task']
        assert original['source_evidence']==cards[uid]['payload']['source_evidence']
        key=cards[uid]['domain']
        counts[key+'_original_sources']+=len(original['source_evidence'])
        counts[key+'_selected_sources']+=len(exposed)
        if original['source_evidence']==exposed:
            counts['exact_reuse']+=1
            assert uid not in child
            continue
        candidate=child[uid]
        # Reject any field delta besides the actor-visible source list.
        user=json.loads(candidate['messages'][1]['content'])
        assert user==dict(original,source_evidence=exposed)
        assert dict(candidate,messages=expected['messages'])==expected
        assert candidate['messages'][0]==expected['messages'][0]
        counts['changed_only_evidence']+=1
        exposure[uid]=sha(candidate)
    assert counts['exact_reuse']==pin['exact_actor_reuse']
    assert counts['changed_only_evidence']==pin['new_actors']==len(child)
    receipts=Counter()
    for f in (OUT/'Actor/visible').glob('*/record.json'):
        row=read(f)
        uid=row['unit']['root_id']
        assert row['request_sha256']==exposure[uid]
        assert row['automatic_retries']==0
        receipts[row['status']]+=1
    return dict(assigned=len(cards),contracts=counts,live_receipts=receipts)


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
