"""Task-conditioned source roles, not a new memory Store or truth guarantee."""
from copy import deepcopy
import json

from qamc.common import parse_object
from .development import text_request

METHODS=['ROLE_STRONG','ROLE_DELTA','ROLE_DELTA_FLAT']
ROLES={'FOLLOW','CONTEXT','IGNORE'}
INTERFACE='''Return only JSON with exactly memory_roles and unresolved_ids.
memory_roles has exactly one {"memory_id":"...","role":"FOLLOW|CONTEXT|IGNORE"}
for every original memory. Use only supplied IDs, no extra fields or explanations.
Preserve the original source boundaries; the Compiler forwards complete original
text, never a newly extracted substring or generated summary.

FOLLOW: the original source warrants a useful current choice, expression,
personal constraint or requested representation within the actual task. A useful
soft preference is enough; it need not be necessary or repeated by the query.
The source does not gain broader scope, stronger force or factual certainty.
CONTEXT: relevant information about the user or another source that can help
interpret the task, understand a viewpoint, or identify/correct a relevant
misunderstanding, but does not warrant adopting it as a current preference,
requirement, world fact or policy. Retaining data is different from endorsing it.
IGNORE: no warranted influence or interpretive need for this current task.
Do not put unrelated memories into CONTEXT merely to avoid making a decision.

For unresolved applicability use IGNORE and include the ID in unresolved_ids,
as in the frozen uncertainty policy. An ID in unresolved_ids cannot be FOLLOW
or CONTEXT. These roles are fallible predictions, not user instructions, source
rewrites, native influence labels or a certificate that the source is true.
The final Actor receives original text plus roles, not your analysis. CONTEXT
is not text-level PARTIAL and is not the benchmark's support-intensity class.
'''
REVIEW='''\nPerform the strongest ordinary query-conditioned review you can in this one
selection. Examine the original request, source ownership, time, scope, negation,
conditions, intended recipient, actual beneficiary and relevant task facts.
Keep helpful soft preferences and valid negative constraints, including sources
whose value becomes clear jointly. Respect changed preferences without treating
every new interest as a replacement. Assess formatting separately from persona
or private conversational style. Neither formality nor a different domain is
by itself a reason to reject a useful preference.

Check both inclusion and exclusion. A related source may still be unsuitable
as a current choice criterion; another may be useful only as attributed context.
Do not turn beliefs into world facts, old habits into universal requirements,
or user tastes into other people's needs. Source identity, historical context
and private signature preferences require independent scrutiny. When the task
requests an account of beliefs or experiences, preserve attribution and answer
that request, rather than unnecessarily rejecting the content.

Consider the original evidence as a whole and choose the best role for every
source under the three-role interface. The final answer should remain complete,
grounded, and appropriately personalized. Do not optimize a count, speculate
about hidden evaluation labels, or invent a plan to make an unrelated memory
useful. Return only the requested JSON; there is no later reviewer or repair.
'''
DELTA='''\nSeparate two decisions: is information useful to understand this task, and
does it have warrant to guide the current response? A truthful description that
the user believes or habitually does something does not itself establish a world
claim, a desired outcome, or a present restriction. Relevant information can be
CONTEXT without being followed. Do not force it into FOLLOW to avoid losing it.

For FOLLOW identify a concrete benefit WITHIN the original goal and actual
roles; helpful optional tastes count, not only indispensable information.
Then check whether that benefit depends on treating a technique's claimed
superiority as truth, preserving an old parameter despite the requested change,
inventing a beneficiary, or importing a new objective. Distinguish desired ends,
ethical choices, avoidances and personal conditions from beliefs about effective
means. A causal conviction or repeated technique is not by itself a binding
restriction. Conversely, a subjective value or reported personal condition need
not be objective science to be a legitimate constraint. Classify meaning, not
the presence of words such as belief, always, or prefer.

Read descriptions of the same practice together: a habit and its supporting
opinion can express one instrumental viewpoint rather than independent evidence
for a current requirement. Do not delete useful surrounding context merely
because it should not be endorsed. CONTEXT can preserve the information needed
to avoid or correct that mistaken inference; it must not change the task's
objective or become a covert constraint. No dependency closure adds sources.

Respect the task's speech act. An explanation of an individual's outlook can
use attributed views without validating them universally; an objective document
must not promote an opinion into established evidence. A valid current request
to express a viewpoint can warrant FOLLOW as representation, not world truth.
When earlier tastes are flexible or an apparent use only advertises an old
interest, keep the requested direction primary. Protect valid joint/negative
constraints and useful style, without manufacturing a need for every memory.
Return only the same three-role JSON. Do not generate an answer or use note.
'''
ACTOR_CONTRACT='''\n\nMemory-role reading contract for this run:
Some memories are JSON cards with memory_id, role and source_text. The role is a
fallible task-conditioned prediction; verify its use against the actual query
and complete original source, including conditions, attribution and time.
FOLLOW may inform the supported choices or expression within this task. It
does not strengthen a soft preference, establish a world claim, or override a
current instruction. Requested representations of views remain attributed.
CONTEXT is information ABOUT a user/viewpoint/history, not an instruction,
current requirement, or objective proof. Use it only where needed to interpret
the task or address a relevant misunderstanding, not as an extra recommendation
criterion. Do not echo background just to display personalization.
If entries have no role cards, apply the base memory-use policy normally.
Never treat card metadata as stronger authority than the original source or
the present request. Complete the requested deliverable using allowed general
knowledge and the shared fixed facts. These labels do not guarantee correctness.
'''


def selector_request(task,method,prompts):
    if method not in METHODS[:2]:raise ValueError('Flat uses the same saved ROLE_DELTA prediction')
    marker='Return only JSON with exactly preference_actions and unresolved_ids, with exactly one action per input memory.'
    base=prompts['style_selector']
    if base.count(marker)!=1:raise ValueError('Frozen S0 interface boundary changed')
    system=base.split(marker)[0]+INTERFACE+(REVIEW if method=='ROLE_STRONG' else DELTA)
    return text_request(system,task.payload(),cap=8192)


def decode(task,raw):
    obj=parse_object(raw)
    if not isinstance(obj,dict) or set(obj)!={'memory_roles','unresolved_ids'}:
        raise ValueError('Expected only source roles and unresolved IDs')
    originals={m.memory_id:m for m in task.memories};task.payload()
    if not isinstance(obj['memory_roles'],list):raise ValueError('Role rows must be a list')
    roles={}
    for row in obj['memory_roles']:
        if not isinstance(row,dict) or set(row)!={'memory_id','role'}:raise ValueError('Unexpected role fields')
        mid,role=row['memory_id'],row['role']
        if not isinstance(mid,str) or mid not in originals or mid in roles or not isinstance(role,str) or role not in ROLES:
            raise ValueError('Unknown/repeated source or unsupported role')
        roles[mid]=role
    if set(roles)!=set(originals):raise ValueError('Every original memory needs exactly one role')
    unresolved=obj['unresolved_ids']
    if not isinstance(unresolved,list) or any(not isinstance(x,str) for x in unresolved) or len(unresolved)!=len(set(unresolved)):
        raise ValueError('Invalid unresolved IDs')
    if any(x not in roles or roles[x]!='IGNORE' for x in unresolved):raise ValueError('Unresolved must remain ignored')
    return {'memory_roles':[{'memory_id':m.memory_id,'role':roles[m.memory_id]} for m in task.memories],
            'unresolved_ids':deepcopy(unresolved)}


def actor(task,raw,prompts,bridge,flat=False):
    decision=decode(task,raw);roles={r['memory_id']:r['role'] for r in decision['memory_roles']}
    evidence=[{'memory_id':m.memory_id,'text':m.text,'role':roles[m.memory_id]}
              for m in task.memories if roles[m.memory_id]!='IGNORE']
    # Source order and complete original text are identical in the role and
    # Flat presentations. No excluded source is reintroduced as a warning.
    values=[e['text'] if flat else json.dumps({'memory_id':e['memory_id'],'role':e['role'],
        'source_text':e['text']},ensure_ascii=False) for e in evidence]
    # An empty evidence view needs no new role-reading instructions and stays
    # exactly compatible with the existing empty-memory Actor cache.
    system=bridge.render(values,'qwen3.8-flash',bridge.blobs['GEPA'].decode())+(ACTOR_CONTRACT if evidence else '')
    user={'query':task.query,'current_context':task.current_context,'fixed_facts':list(task.fixed_facts)}
    return {'request':text_request(system,user,cap=4096),'roles':decision,
        'view':{'query':task.query,'current_context':task.current_context,'facts':list(task.fixed_facts),
                'source_evidence':deepcopy(evidence)},
        'input_audit':{'raw_text_unchanged':True,'source_order_preserved':True,'role_tags_visible':bool(evidence) and not flat,
            'role_contract_active':bool(evidence),
            'same_common_actor_contract_in_all_arms':True,'hard_semantic_isolation':False,
            'no_reference_answer':True,'role_flat_is_saved_prediction_ablation':flat}}
