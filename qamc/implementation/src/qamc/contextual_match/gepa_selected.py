"""Frozen Strong admission with released GEPA generation; no new predictions.

Flat and bounded arms share byte-identical selected original texts and system
policy. Guidance indices refer to their ordered positions in that memory list,
not the original IDs, which the released renderer does not expose.
"""
from copy import deepcopy

from . import behavioral_probes
from .development import text_request

METHODS = ['GEPA_SELECTED_FLAT', 'GEPA_SELECTED_BOUNDS']


def actor(task, selector_answer, prompts, bridge, method):
    if method not in METHODS:raise ValueError('Unknown selected GEPA arm')
    compiled = behavioral_probes.actor(task, selector_answer, prompts)
    evidence = compiled['view']['source_evidence']
    texts = [r['text'] for r in evidence]
    system = bridge.render(texts, 'qwen3.8-flash', bridge.blobs['GEPA'].decode())
    bounded = method == 'GEPA_SELECTED_BOUNDS'
    # Identical public container in both arms; only the guidance differs.
    user = {'query':task.query,'current_context':task.current_context,'fixed_facts':list(task.fixed_facts)}
    guidance = [{'memory_position_1_based':i+1,'use_instruction':compiled['use_bounds'][r['memory_id']]}
        for i,r in enumerate(evidence)]
    if bounded and guidance:user['selected_memory_use_guidance'] = guidance
    request = text_request(system,user,cap=4096)
    return {'request':request,'selection':compiled['selection'],
        'view':{'query':task.query,'current_context':task.current_context,'facts':list(task.fixed_facts),
            'source_evidence':deepcopy(evidence),
            **({'memory_use_instructions':deepcopy(compiled['view'].get('memory_use_instructions',[]))} if bounded else {})},
        'audit':{'no_new_selector':True,'complete_released_policy':True,
            'compiled_original_texts_in_author_order':texts,'guidance_index_to_original_id':[
                {'position_1_based':i+1,'memory_id':r['memory_id']} for i,r in enumerate(evidence)],
            'no_rejected_source_reintroduced':True,'bound_guidance_visible':bounded,
            'all_memory_policy_comparison_also_changes_selected_evidence':True}}
