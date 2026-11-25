"""Bounded, equally available development feedback with exact cited evidence.

Unincluded source units are explicitly omitted, not classified as irrelevant or
absent from R. The complete immutable trajectories remain the audit source.
"""
from qamc.common import sha,canonical,token_estimate


def build_packet(experiences,index,max_estimated_tokens=28000):
    def flagged(e):
        d=e.get('source_feedback',{}).get('diagnostic',{})
        return e['feedback'].get('score',{}).get('accuracy')==0 or any(d.get(k) for k in ['unsupported_personal_facts','overuse','underuse'])
    errors=[e for e in experiences if flagged(e)]
    successes=[e for e in experiences if not flagged(e)]
    targets=([errors[index%len(errors)]]if errors else[])+successes[:1]
    summaries=[{'experience_id':sha(e['input'])[:20],'feedback':e['feedback'],'source_feedback':e.get('source_feedback'),'input_hash':sha(e['input'])}for e in experiences]
    examples=[]
    for e in targets:
        trace=e['trace'];refs=set(e['scope']['task_unit_ids'])
        def collect(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    if k=='unit_id'and isinstance(v,str):refs.add(v)
                    elif k in {'source_refs','task_unit_ids','shared_constraint_refs'}and isinstance(v,list):refs.update(t for t in v if isinstance(t,str))
                    else:collect(v)
            elif isinstance(x,list):
                for v in x:collect(v)
        for name,value in trace.items():
            if name!='actor_input':collect(value)
        actor=trace.get('actor_input',{})
        refs.update(u['unit_id']for u in actor.get('source_evidence',[]))
        inp={**e['input'],'units':[u for u in e['input']['units']if u['unit_id']in refs]}
        example={'experience_id':sha(e['input'])[:20],'input':inp,'scope':e['scope'],
            'trace':{k:v for k,v in trace.items()if k!='actor_input'},'feedback':e['feedback'],'source_feedback':e.get('source_feedback'),
            'source_coverage':{'original_units':len(e['input']['units']),'included_units':len(inp['units']),
                'omitted_units_are_not_absent_from_R':True,'complete_input_hash':sha(e['input'])}}
        if not examples and token_estimate(canonical(example))>max_estimated_tokens:
            raise ValueError('one complete target trace exceeds packet capacity; no silent truncation')
        if token_estimate(canonical(examples+[example]))<=max_estimated_tokens:examples.append(example)
    packet={'all_development_feedback':summaries,'source_grounded_examples':examples,
            'example_selection':'one rotating current error, one successful preservation control; no Gold-based source recovery',
            'included_example_count':len(examples),'total_development_examples':len(experiences),
            'limitations':'Not all R is repeated here. Missing evidence in this packet is not proof it was absent from retrieval. Source/scope error attributions remain hypotheses.'}
    if len(canonical(packet).encode())>1_500_000:raise ValueError('bounded feedback packet exceeds transport reserve')
    return packet
