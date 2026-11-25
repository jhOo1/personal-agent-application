"""Compose public inputs and compile one sparse Gate result.

No gateway, dispatch, Store mutation, scorer or evaluation-label access exists in
this pure module. Dispatch is isolated in the experiment runner.
"""
from qamc.bace.prepare import small_bundle
from qamc.pa.engine import raw_view


def public_payload(task):
    """Use the same candidate construction as frozen G0, without a scope call."""
    task.payload()  # Validate unique source identities and source coverage.
    memory_ids={m.memory_id for m in task.memories}
    fact_ids={f'FACT{i}' for i in range(len(task.fixed_facts))}
    if memory_ids & fact_ids:raise ValueError('Memory/fixed-fact identity collision')
    sources=[{'id':m.memory_id,'content':m.text,'role':'user'} for m in task.memories]
    sources += [{'id':f'FACT{i}','content':s,'role':'user'} for i,s in enumerate(task.fixed_facts)]
    payload=small_bundle(task.query,sources)['payload']
    payload['current_context']=[task.current_context] if task.current_context else []
    return payload


def compile_selected(task,payload,selection):
    """Compile original source text; material gaps remain audit-only."""
    if payload!=public_payload(task):raise ValueError('Public candidate payload changed')
    if not isinstance(selection,dict) or set(selection)!={'selected_unit_ids','material_gaps'}:
        raise ValueError('Unexpected selection schema')
    for field in selection:
        values=selection[field]
        if not isinstance(values,list) or not all(isinstance(v,str) for v in values):
            raise ValueError('Selection fields must be string lists')
        if len(values)!=len(set(values)):raise ValueError('Duplicate selection entries')
    units={u['unit_id']:u for u in payload['units']}
    chosen=selection['selected_unit_ids']
    if not set(chosen)<=units.keys():raise ValueError('Unknown unit')
    source_ids={units[uid]['source_id'] for uid in chosen}
    # Match G0's source-level compilation. Selecting a unit restores its entire
    # original memory; no claim of hard span isolation or scope enforcement.
    view=raw_view(task)
    view['source_evidence']=[e for e in view['source_evidence'] if e['memory_id'] in source_ids]
    return view
