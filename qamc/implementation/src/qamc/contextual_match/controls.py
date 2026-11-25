"""Offline-ready controls; not active changes to the frozen P2 experiment.

These builders provide equal-call review, non-isolated joint representation,
and shared-prediction dependency ablations. A later frozen runner must allocate
and log every actual request. No API, evaluator, Store or benchmark router is
imported here.
"""
from copy import deepcopy
from qamc.common import parse_object,sha
from .core import (SCHEMA,exact_keys,memory_payload,task_payload,source_map,
                   validate_field,validate_memory_view,normalize_selection,compile_match)
from .development import text_request
from .prompts import MEMORY,TASK,ATTR_HINT,request
from .representation_replay import recover_memory_view


REVIEW = """\nReview the supplied previous selection against the same original request and
complete original sources. Check for mistakes in either direction: inappropriate
admissions and missing useful evidence or legitimate preferences. Keep correct
decisions; revise only when the public evidence warrants it. Check qualifications,
actual beneficiaries, current constraints and uncertainty without inventing new
requirements. Do not assume fewer or more memories is better. The prior selection
is a fallible proposal, not evidence. Return the same sparse selection JSON only;
do not answer the query, output a critique, or change source text or span IDs.
"""

JOINT_MEMORY=MEMORY.replace(
    'Annotate the supplied allowed historical snapshot without knowing the current query.',
    'Annotate the supplied allowed historical snapshot with the current query and context available. '
    'The original historical sources still determine every attributed property.')
JOINT_TASK=TASK.replace(
    'Read only the current request and its public current context.',
    'Read the current request and its public current context with original history available '
    'to resolve supported historical references.').replace(
    'Anchors may only use source_id query or current_context.',
    'Anchors may use source_id query, current_context, or supplied original historical source IDs.')

JOINT = """Construct memory_view and task_view jointly from all supplied original
sources, query, and current context. Unlike an isolated encoder, you may consider
the complete input while interpreting both views. Preserve sources as authority;
do not answer, select memories, add user goals or predict an applicability policy.
For memory_view use the source schema and attribute guidance inside MEMORY_FIELD
below. For task_view use the task schema and guidance inside TASK_FIELD below.
Their standalone 'return only' instructions apply to the respective field. Return
one outer JSON object with exactly memory_view and task_view.

Task attributes may cite original history when resolving supported references;
preserve provenance and leave unsupported roles unresolved. Every quote and offset
must point to a supplied source. Memory attributes must cite their historical
sources. Unknown does not mean inapplicable. Historical personal interests must
not create new deliverables, participants or goals in the current request.

MEMORY_FIELD:
"""+JOINT_MEMORY+"\nTASK_FIELD:\n"+JOINT_TASK


def review_request(task,previous_selection,style_prompt,model='qwen3.8-flash'):
    # Reject a malformed prior proposal instead of quietly repairing its meaning.
    normalize_selection(task,previous_selection)
    return text_request(style_prompt+REVIEW,
        {'original_input':task.payload(),'previous_selection':deepcopy(previous_selection)},model,8192)


def joint_request(task,model='qwen3.8-flash'):
    # Exactly the union available to the two isolated encoders. Historical F is
    # absent here as in M1/M2a; it remains present later at the shared selector.
    payload={**memory_payload(task),**task_payload(task)}
    # Combined output allowance equals two isolated 8192 caps; realized compute
    # is still different and must be reported, not asserted equal by this setting.
    return text_request(JOINT,payload,model,16384)


def validate_joint_task(task,view):
    exact_keys(view,{'schema','deliverables','roles','constraints','unresolved_mentions'})
    if view['schema']!=SCHEMA:raise ValueError('Joint TaskView schema mismatch')
    sources={**source_map(task,'memory'),**source_map(task,'task')}
    for name in ('deliverables','roles','constraints','unresolved_mentions'):
        if not isinstance(view[name],list):raise ValueError('Joint TaskView collection must be a list')
        for field in view[name]:validate_field(field,sources,task_side=True)
    return deepcopy(view)


def decode_joint(task,answer):
    obj=parse_object(answer)
    exact_keys(obj,{'memory_view','task_view'})
    recovered=recover_memory_view(task,obj['memory_view'])
    return {'memory_view':recovered['view'],'task_view':validate_joint_task(task,obj['task_view']),
            'mechanical_events':recovered['events'],'joint_encoder_sha256':sha(obj)}


def joint_selector_request(task,view,style_prompt,model='qwen3.8-flash'):
    memory=validate_memory_view(task,view['memory_view'])
    task_view=validate_joint_task(task,view['task_view'])
    return text_request(style_prompt+ATTR_HINT,
        {**task.payload(),'memory_view':memory,'task_view':task_view},model,8192)


def typed_request(task,memory_view,task_view,style_prompt,model='qwen3.8-flash'):
    return request('Selector',task,model,8192,style_prompt,'R4',memory_view,task_view)


def dependency_actor_pair(task,prediction,actor_prompt,model='qwen3.8-flash'):
    # One matcher prediction, two deterministic executions, identical Actor
    # system/backbone/cap. Changed evidence is the only generation difference.
    result={}
    for name,closure in (('R4',False),('R5',True)):
        compiled=compile_match(task,prediction,closure)
        result[name]={**compiled,'request':text_request(actor_prompt,compiled['view'],model,4096)}
    if result['R4']['audit']['matcher_sha256']!=result['R5']['audit']['matcher_sha256']:
        raise ValueError('Dependency ablation changed the matcher prediction')
    return result
