"""Compact full-R feedback for one target and a source-grounded success control.

The source table is lossless and contains no additional retrieval. Original unit
ids are aliased only in optimizer feedback, never in inference/Actor requests.
"""
from copy import deepcopy
import re
from .policy_targets import eligible_target
from qamc.common import canonical,sha,token_estimate


def compact_input(payload):
    units=payload['units']
    already_short=all(re.fullmatch(r'U[1-9]\d*|Q0',u['unit_id'])for u in units)
    aliases={u['unit_id']:u['unit_id']if already_short else f'U{i:04d}'for i,u in enumerate(units,1)}
    meta={};rows=[]
    columns=['unit_id','source_id','start','end','exact_text']
    for u in units:
        sid=u['source_id'];m={k:v for k,v in u.items()if k not in columns}
        if sid in meta and meta[sid]!=m:raise ValueError('unit-specific metadata cannot be silently compacted')
        meta[sid]=m;rows.append([aliases[u['unit_id']],sid,u['start'],u['end'],u['exact_text']])
    body={k:deepcopy(v)for k,v in payload.items()if k!='units'}
    # Source-level navigation and per-unit metadata are different objects. Keep
    # both; overwriting the existing source table would lose epoch-v2 context.
    body.update(unit_columns=columns,unit_rows=rows,unit_metadata_by_source=meta)
    navigation=body.pop('profile_navigation',None)
    if navigation is not None:
        keys=list(dict.fromkeys(k for row in navigation for k in row))
        body['profile_table']={'columns':keys,'rows':[[row.get(k)for k in keys]for row in navigation]}
        if any(set(row)!=set(keys)for row in navigation):
            body['profile_table']['present_keys']=[list(row)for row in navigation]
    return body,aliases


def restore_input(compact,aliases):
    reverse={v:k for k,v in aliases.items()};units=[]
    for row in compact['unit_rows']:
        u=dict(zip(compact['unit_columns'],row));u['unit_id']=reverse[u['unit_id']]
        u.update(compact['unit_metadata_by_source'][u['source_id']]);units.append(u)
    out={**{k:deepcopy(v)for k,v in compact.items()if k not in {'unit_columns','unit_rows','unit_metadata_by_source','profile_table'}},'units':units}
    if 'profile_table'in compact:
        table=compact['profile_table']
        present_keys=table.get('present_keys',[table['columns']]*len(table['rows']))
        out['profile_navigation']=[{k:v for k,v in zip(table['columns'],row)if k in present}
                                   for row,present in zip(table['rows'],present_keys)]
    return out


def remap(value,aliases):
    if isinstance(value,str):return aliases.get(value,value)
    if isinstance(value,list):return [remap(v,aliases)for v in value]
    if isinstance(value,dict):return {k:remap(v,aliases)for k,v in value.items()}
    return value


def build_packet(experiences,index,max_estimated_tokens=90000):
    errors=[e for e in experiences if eligible_target(e)];successes=[e for e in experiences if not eligible_target(e)]
    successes.sort(key=lambda e:sum(len(e.get('source_feedback',{}).get('diagnostic',{}).get(k,[]))for k in ['unsupported_personal_facts','overuse','underuse']))
    selected=([errors[index%len(errors)]]if errors else[])+successes[:1]
    summaries=[]
    for e in experiences:
        d=e.get('source_feedback',{}).get('diagnostic',{})
        summaries.append({'experience_id':sha(e['input'])[:20],'native_feedback':e['feedback'],
            'reference_interpretation_note':e.get('reference_dispute'),
            'eligible_as_error_target':eligible_target(e),
            'fixed_choice_caveat':'A source-Judge complaint against a natively correct fixed option is an unresolved evaluator disagreement, not an editable claim or a reason to resample option formatting.',
            'automatic_diagnostic_counts':{k:len(d.get(k,[]))for k in ['unsupported_personal_facts','overuse','underuse','uncertain']},
            'automatic_task_faithfulness':d.get('task_faithfulness')})
    examples=[]
    for i,e in enumerate(selected):
        # The target receives ALL frozen R, so missing-source hypotheses can be
        # checked. The preservation control needs its selected and flagged evidence.
        p=deepcopy(e['input'])
        if i>0:
            refs=set(e['scope']['task_unit_ids'])
            def collect(x):
                if isinstance(x,dict):
                    for k,v in x.items():
                        if k=='unit_id'and isinstance(v,str):refs.add(v)
                        elif k in {'source_refs','selected_unit_ids','task_unit_ids','shared_constraint_refs'}and isinstance(v,list):refs.update(t for t in v if isinstance(t,str))
                        else:collect(v)
                elif isinstance(x,list):
                    for v in x:collect(v)
            collect(e['trace']);collect(e.get('source_feedback',{}));p['units']=[u for u in p['units']if u['unit_id']in refs]
        packed,aliases=compact_input(p)
        if restore_input(packed,aliases)!=p:raise ValueError('optimizer source compaction is not lossless')
        example={'experience_id':sha(e['input'])[:20],'input':packed,'scope':remap(e['scope'],aliases),
            'trace':remap({k:v for k,v in e['trace'].items()if k!='actor_input'},aliases),
            'feedback':e['feedback'],'source_feedback':remap(e.get('source_feedback',{}),aliases),
            'reference_interpretation_note':e.get('reference_dispute'),
            'source_coverage':{'original_units':len(e['input']['units']),'included_units':len(p['units']),
                'omitted_units_are_not_absent_from_R':True,'full_R_included':i==0,'original_input_hash':sha(e['input'])}}
        trial={'all_development_feedback':summaries,'source_grounded_examples':examples+[example]}
        if token_estimate(canonical(trial))>max_estimated_tokens:
            if not examples:raise ValueError('full target R exceeds feedback capacity; no silent truncation or true-call debugging')
            continue
        examples.append(example)
    packet={'all_development_feedback':summaries,'source_grounded_examples':examples,
        'representation':'unit_columns decode unit_rows; unit aliases are local to each example. unit_metadata_by_source restores repeated unit fields; source_metadata preserves the original source navigation. profile_table columns decode rows; optional present_keys distinguishes absent fields from null (if absent, every column is present). Full raw text/offsets and target Profile preserved.',
        'included_example_count':len(examples),'total_development_examples':len(experiences),
        'limits':'Diagnostic labels are model predictions. No gold answer/option text is recovered from the native score. A partial preservation example is marked; it is not evidence that omitted units were absent from R.'}
    if len(canonical(packet).encode())>1_500_000:raise ValueError('feedback capacity reserve exceeded')
    return packet
