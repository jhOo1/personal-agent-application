"""Compare Scope and archived SELECTED_GEPA using verified adapted Judge inputs."""
from collections import Counter,defaultdict
import json

from compare_controls import load_verified_scores
from complete import get_author,normalized,passes,persist
from expansion_run import OUT,read
from qamc.common import sha


def compare():
    _,envelopes,_=get_author()
    selected,_=load_verified_scores()
    totals=defaultdict(Counter)
    availability=Counter()
    for batch in range(1,4):
        folder=OUT/f'batch_{batch}'
        wires={(r['unit']['root_id'],r['unit']['method']):r['request']
               for r in read(folder/'private/PersistNative_MANIFEST.json')['units']}
        returned={}
        for path in (folder/'PersistNative/visible').glob('*/record.json'):
            receipt=read(path)
            key=receipt['unit']['root_id'],receipt['unit']['method']
            if sha(wires[key])!=receipt['request_sha256']:
                raise ValueError('PersistBench request hash changed')
            if receipt['status']=='OK':
                returned[key]=read(path.with_name('response.json'))['answer']
        for row in read(folder/'RESULTS.json')['rows']:
            if row['benchmark']!='PersistBench' or row['method']!='SCOPE':
                continue
            uid,track=row['uid'],row['stratum']
            availability['assigned']+=1
            if row['score'] is None or uid not in selected:
                availability['score_missing']+=1
                continue
            key=uid,'SCOPE/'+persist.STAGE
            if key not in wires:
                availability['physical_scope_wire_unavailable']+=1
                continue
            saved_track,saved_score=selected[uid]
            if (normalized(wires[key],row['answer'])!=envelopes[uid]
                    or row['raw_scores'][persist.STAGE]!=returned[key]
                    or saved_track!=track):
                raise ValueError('PersistBench comparator provenance changed')
            new,old=passes(row['score'],track),passes(saved_score,track)
            for bucket in ('all',track):
                totals[bucket].update(common=1,scope_pass=new,selected_gepa_pass=old,
                                      wins=new and not old,losses=old and not new)
    return dict(availability=availability,paired=totals)


if __name__=='__main__':
    print(json.dumps(compare(),indent=2))
