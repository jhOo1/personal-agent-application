"""Audit which original memories were actually sent by the unified external selector."""
from collections import Counter, defaultdict
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[2]/'runs'/HERE.parent.name/HERE.name
EXTERNAL = RUN.with_name(RUN.name+'_self_recheck')


def read(path):
    return json.loads(path.read_text())


def main():
    cards = {row['uid']:row for row in read(RUN/'private/FROZEN.json')['rows']}
    manifest = read(EXTERNAL/'private/Actor_MANIFEST.json')
    labels = {r['uid']:r['labels'] for r in read(HERE.parent/'ipe_c_two_endpoint_completion_v1/RESULTS.json')['rows']}
    exposures = defaultdict(Counter)
    rpe = defaultdict(Counter)
    bench = defaultdict(Counter)
    seen = set()
    for unit in manifest['units']:
        uid = unit['unit']['root_id']
        assert uid not in seen
        seen.add(uid)
        card = cards[uid]
        payload = json.loads(unit['request']['messages'][1]['content'])
        sources = card['payload']['source_evidence']
        retained = payload['source_evidence']
        assert payload['task']==card['payload']['task']
        ids = {s['memory_id'] for s in retained}
        assert retained==[s for s in sources if s['memory_id'] in ids]
        domain = card['domain']
        for key in (domain,domain+'/'+card['stratum']):
            counter = exposures[key]
            counter.update(actors=1,available_sources=len(sources),exposed_sources=len(ids),
                           empty=not ids,all=len(ids)==len(sources))
        if domain=='RPEval':
            assert [s['memory_id'] for s in sources]==[f'M{i}' for i in range(len(sources))]
            for item,label in zip(sources,labels[uid],strict=True):
                rpe[label].update(total=1,retained=item['memory_id'] in ids)
        elif domain=='BenchPreS':
            # Measure only a unique verbatim link. Ambiguity is retained separately.
            for score in card['base_score']['decisions']:
                key='appropriate' if score['appropriate'] else 'inappropriate'
                pref=score['preference'].strip()
                matches=[s['memory_id'] for s in sources if pref and pref in s['text']]
                if len(matches)==1:
                    bench[key].update(uniquely_aligned=1,retained=matches[0] in ids)
                else:
                    bench[key].update(unresolved=1)
    print(json.dumps(dict(assigned=len(cards),actor_wires=len(seen),exposures=exposures,rpe=rpe,bench=bench),indent=2))


if __name__=='__main__':
    main()
