"""Check that the three expansion paths share every intended input."""
from argparse import ArgumentParser
from collections import Counter,defaultdict
import json

from expansion_run import OUT,read
from trial import HERE,sha


def manifest(directory,stage):
    file=directory/'private'/f'{stage}_MANIFEST.json'
    if not file.exists():
        return {}
    found={}
    for entry in read(file)['units']:
        key=entry['unit']['root_id'],entry['unit']['method']
        assert key not in found
        found[key]=entry['request']
    return found


def exposure_counts(cards, selected):
    """Count selected original sources, using author labels only in this audit."""
    endpoint=HERE.parent/'ipe_c_two_endpoint_completion_v1'/'RESULTS.json'
    labels={r['uid']:r['labels'] for r in read(endpoint)['rows']}
    exposure=defaultdict(Counter)
    rpe=defaultdict(Counter)
    bench=defaultdict(Counter)
    for uid,card in cards.items():
        domain=card['domain']
        sources=card['payload']['source_evidence']
        chosen=selected.get(uid)
        keys=(domain, f"{domain}/{card['stratum']}")
        for key in keys:
            exposure[key].update(assigned=1, manifest_available=chosen is not None)
        if chosen is None:
            continue
        ids={s['memory_id'] for s in chosen}
        for key in keys:
            exposure[key].update(candidate_sources=len(sources),actor_sources=len(ids),
                                 empty_selection=not ids)
        if domain=='RPEval':
            assert [s['memory_id'] for s in sources]==[f'M{i}' for i in range(len(sources))]
            for source,label in zip(sources,labels[uid],strict=True):
                rpe[label].update(candidate=1,actor=source['memory_id'] in ids)
        elif domain=='BenchPreS':
            for score in card['base_score']['decisions']:
                key='appropriate' if score['appropriate'] else 'inappropriate'
                preference=score['preference'].strip()
                matches=[s['memory_id'] for s in sources if preference and preference in s['text']]
                if len(matches)==1:
                    bench[key].update(uniquely_aligned=1,actor=matches[0] in ids)
                else:
                    bench[key].update(unresolved=1)
    return dict(by_task_slice=exposure,rpe_author_labels=rpe,bench_literal_links=bench)


def audit(index):
    frozen=read(OUT/'private/FROZEN.json')
    cards={r['uid']:r for r in frozen['batches'][index-1]}
    folder=OUT/f'batch_{index}'
    plan=manifest(folder,'Plan')
    select=manifest(folder,'Select')
    actor=manifest(folder,'Actor')
    selected={}
    for stage,wires in (('Plan',plan),('Select',select)):
        for key,request in wires.items():
            uid,method=key
            assert method=='shared'
            payload=json.loads(request['messages'][1]['content'])
            assert sha(request)==cards[uid][stage.lower().replace('select','selection')+'_sha']
            if stage=='Plan':
                assert payload=={'task':cards[uid]['payload']['task']}
            else:
                assert set(payload)=={'question','retrieved_memories'}
                assert all(set(m)=={'content','memory_id'} for m in payload['retrieved_memories'])
                assert payload['question']==cards[uid]['payload']['task']['query']
                assert [m['content'] for m in payload['retrieved_memories']]==[
                    m['text'] for m in cards[uid]['payload']['source_evidence']]
    for (uid,arm),w in actor.items():
        original=cards[uid]['payload']
        p=json.loads(w['messages'][1]['content'])
        assert p['task']==original['task']
        chosen=p['source_evidence']
        ids={s['memory_id'] for s in chosen}
        assert chosen==[s for s in original['source_evidence'] if s['memory_id'] in ids]
        assert chosen==selected.setdefault(uid,chosen)
        if arm=='SCOPE':
            base=actor[uid,'PLAN_SELECTED']
            system=base['messages'][0]['content']+'\n\n'+frozen['scope_edit']['instruction']
            assert w==dict(base,messages=[dict(base['messages'][0],content=system),*base['messages'][1:]])
        elif arm=='DIRECT':
            assert set(p)=={'task','source_evidence'}
    counts=defaultdict(Counter)
    for stage,wires in (('Plan',plan),('Select',select),('Actor',actor)):
        for path in (folder/stage/'visible').glob('*/record.json'):
            r=read(path)
            key=r['unit']['root_id'],r['unit']['method']
            assert sha(wires[key])==r['request_sha256']
            assert r['automatic_retries']==0
            counts[stage][r['status']]+=1
    distinct={key:len({c[f'{key}_sha'] for c in cards.values()}) for key in ('plan','selection')}
    assert len(plan)<=distinct['plan'] and len(select)<=distinct['selection']
    if plan:
        assert {sha(w) for w in plan.values()}=={c['plan_sha'] for c in cards.values()}
    return dict(index=index,assigned=len(cards),distinct_upstream_requests=distinct,verified_physical_manifests={
                    'Plan':len(plan),'Select':len(select),'Actor':len(actor)},
                scope_parent_exact_input_pairs=sum(key[1]=='SCOPE' for key in actor),
                verified_receipts=counts, evidence_exposure=exposure_counts(cards,selected))


if __name__=='__main__':
    cli=ArgumentParser(description=__doc__)
    cli.add_argument('batch',type=int,choices=(1,2,3))
    print(json.dumps(audit(cli.parse_args().batch),indent=2))
