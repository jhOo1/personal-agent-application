"""Evaluation-only exposure strata; they are not causal or semantic labels."""
import json
from qamc.common import sha
from .evaluation import unique_index,aggregate
from .actor_window_analysis_v2 import PAIRS


def classify_request(request):
    if request is None:return {'stratum':'MISSING_BASE_SELECTION'}
    messages=request['messages']
    if len(messages)!=2 or [m['role'] for m in messages]!=['system','user']:
        raise ValueError('Unexpected Actor history: exposure must be inspected explicitly')
    view=json.loads(messages[1]['content']);sources=view['source_evidence'];facts=view['facts']
    if set(view)-{'query','current_context','facts','source_evidence','source_kind_annotations','annotation_notice'}:
        raise ValueError('Unknown Actor field may contain additional evidence')
    annotations=view.get('source_kind_annotations',[])
    if {a['memory_id'] for a in annotations}-{s['memory_id'] for s in sources}:
        raise ValueError('Annotation exposes an excluded source')
    context=view['current_context']
    if not isinstance(context,str) or not isinstance(facts,list):raise ValueError('Unknown current-input schema')
    kind=('SELECTED_ORIGINAL_MEMORY' if sources else 'NO_SELECTED_MEMORY_WITH_FACTS_OR_CONTEXT'
          if facts or context.strip() else 'QUERY_ONLY_NO_SELECTED_MEMORY')
    return {'stratum':kind,'selected_source_count':len(sources),'fact_entries':len(facts),
            'context_characters':len(context),'type_annotation_count':len(annotations),
            'fixed_user_fields_sha256':sha({k:view[k] for k in ('query','current_context','facts','source_evidence')}),
            'system_sha256':sha(messages[0]['content']),'user_sha256':sha(messages[1]['content']),
            'request_sha256':sha(request),'actual_message_count':len(messages)}


def diagnostic(cases,jobs,rows,methods,expected_systems=None):
    planned={(j['unit']['root_id'],j['unit']['method']):j['request'] for j in jobs}
    if len(planned)!=len(jobs):raise ValueError('Duplicate Actor identity')
    if expected_systems is not None:
        for (_,method),request in planned.items():
            if request['messages'][0]['content']!=expected_systems[method]:
                raise ValueError('Actor system prompt differs from the frozen generic template')
    exposures=[];groups={};index=unique_index(rows);by_uid={c['uid']:c for c in cases}
    for c in cases:
        values={m:classify_request(planned.get((c['uid'],m))) for m in methods}
        strata={v['stratum'] for v in values.values()}
        if len(strata)!=1:raise ValueError('Methods differ in raw source exposure')
        raw={v['fixed_user_fields_sha256'] for v in values.values() if 'fixed_user_fields_sha256' in v}
        if len(raw)>1:raise ValueError('Methods differ in raw current input or source bag')
        group=next(iter(strata));groups.setdefault(group,[]).append(c)
        exposures.append({'uid':c['uid'],'benchmark':c['benchmark'],'stratum':group,'by_method':values})
    pairs=[];changes=[]
    for stratum,selected in sorted(groups.items()):
        for benchmark in ('rpeval','benchpres','persistbench'):
            chosen=[c for c in selected if c['benchmark']==benchmark]
            if not chosen:continue
            for left,right in PAIRS:
                common=[c['uid'] for c in chosen if all((c['uid'],m) in index and index[c['uid'],m].get('score') is not None for m in (left,right))]
                a=aggregate(benchmark,[index[u,left] for u in common],by_uid)
                b=aggregate(benchmark,[index[u,right] for u in common],by_uid)
                pairs.append({'stratum':stratum,'benchmark':benchmark,'left':left,'right':right,
                    'selected_roots':len(chosen),'common_scored_roots':len(common),'uids':common,
                    'left_metrics':a,'right_metrics':b,
                    'delta_left_minus_right':{k:a[k]-b[k] if a[k] is not None and b[k] is not None else None for k in a}})
                if stratum=='QUERY_ONLY_NO_SELECTED_MEMORY':
                    for uid in common:
                        av=aggregate(benchmark,[index[uid,left]],by_uid);bv=aggregate(benchmark,[index[uid,right]],by_uid)
                        if av!=bv:changes.append({'uid':uid,'left':left,'right':right,
                            'left_metrics':av,'right_metrics':bv,'same_raw_fields':True,
                            'historical_source_injection_effect_not_identified':True})
    return {'exposures':exposures,'paired_by_exposure':pairs,'query_only_scored_differences':changes,
            'stratum_selected_counts':{g:len(v) for g,v in groups.items()},
            'posthoc_diagnostic_not_promotion_rule':True,'no_confidence_or_causal_claim':True,
            'generic_system_prompts_verified':expected_systems is not None,
            'query_may_itself_express_preferences':True,'provider_hidden_state_not_verified':True,
            'no_source_stratum_not_a_randomized_no_memory_control':True,
            'scores_modified':False,'new_model_calls':0,'human_reviews':0}
