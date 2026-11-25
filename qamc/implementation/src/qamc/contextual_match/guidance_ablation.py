"""Formal deletion ablation of frozen C5/C6 guidance, no new method policy.

No source is judged, added, removed or rewritten. Only the optional, already
predicted use-guidance field is omitted from the unchanged Actor's public User.
"""
from copy import deepcopy
import json
from qamc.common import sha
from . import goal_effect,goal_effect_gepa

METHODS=['EFFECT_TASK_NO_GUIDANCE','EFFECT_GEPA_NO_GUIDANCE']


def actor(task,raw,prompts,bridge,method):
    if method not in METHODS:raise ValueError('Unknown formal ablation arm')
    original=(goal_effect if method==METHODS[0] else goal_effect_gepa).actor(task,raw,prompts,bridge)
    built=deepcopy(original);request=built['request']
    payload=json.loads(request['messages'][1]['content'])
    removed=payload.pop('selected_memory_use_guidance',None)
    request['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
    built['view'].pop('memory_use_instructions',None)
    built['audit']['bound_guidance_visible']=False
    built['ablation_audit']={'original_bounded_request_sha256':sha(original['request']),
        'same_selected_original_sources':True,'same_actor_system':True,'new_selector_calls':0,
        'new_policy_words':0,'removed_guidance_records':len(removed or []),
        'request_changed':request!=original['request'],'is_formal_component_ablation_not_candidate7':True}
    return built
