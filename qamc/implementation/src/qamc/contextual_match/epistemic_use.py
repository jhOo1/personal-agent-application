"""Query-anchored information support, shared with a source-scope control.

Quotes establish provenance only. DIRECT and other semantic assessments remain
fallible model predictions; this is not a modal-logic planner or truth oracle.
"""
from copy import deepcopy
import json

from qamc.common import parse_object
from .committed_use import COMMON

BINDER = COMMON + """
Return only {"memory_use_instructions":[{"memory_id":"...",
"use_instruction":"..."}],"needs":[{"id":"N1",
"kind":"PERSONAL_INFORMATION|TASK_CONDITION","need":"...","anchor":"...",
"status":"DIRECT|RELATED_ONLY|MISSING|GENERAL_INFERENCE",
"evidence":[{"source_id":"...","quote":"..."}]}]}.

First identify at most3 important information requirements or success conditions
of the ORIGINAL query/context, not goals created by historical interests. An
information need is not its answer. Use an exact current-query/context anchor.
PERSONAL_INFORMATION needs a person's specific value, event, time, relationship,
or explanation; TASK_CONDITION is an existing requested outcome or a condition
needed for it to work. Do not turn every useful preference into a prerequisite.
Do not ask for details that are unnecessary for giving useful conditional advice.
No needs is valid when the additional representation is unnecessary.

Assess the actual support from supplied originals, including the current query:
DIRECT: the requested proposition/relationship is supported; cite exact evidence.
RELATED_ONLY: there is nearby information but the needed value/relationship is
not established; cite that nearby evidence without filling the gap.
MISSING: no supplied evidence establishes it; use empty evidence[].
GENERAL_INFERENCE: a TASK_CONDITION reasonably inferred from the requested goal,
not a private user fact. Do not use this status for PERSONAL_INFORMATION.
Unrelated known events do not establish causation, chronology, participation or
identity merely because they can be woven into a plausible story. A source
snapshot is not exhaustive knowledge of the world. Missing does not mean false,
zero, completed, or permission to invent a value. Distinguish legitimate useful
preferences, requested viewpoints and task success from asserted personal facts.

F0,F1,... identify the original fixed-fact entries; query/current_context are
also evidence IDs. Their headings are metadata, not personal facts. Memory IDs
identify only the committed original excerpts shown. Never cite unseen sources.
Use N1,N2,N3 in order. Each need/anchor is <=240 characters and a need <=50 words.
Each need has <=3 exact evidence quotes, each <=500 characters. DIRECT and
RELATED_ONLY require evidence; MISSING forbids it. These are fallible assessments.

Also give exactly one memory_use_instructions record per committed memory, in
input order. State its concrete helpful influence and limits within this task.
Protect useful soft preferences and continuing constraints. A person's belief
is not objective evidence, and an unsuccessful old outcome is not automatically
a continuing requirement. Respect explicitly requested portrayals/stances.
Each note is <=80 words/700 characters. If there is no justified influence, say
so; you may not remove or rewrite the committed original. No answer, option
ranking, new personal fact, source rewriting, or user-profile update.
"""


def public_payload(original):
    value=json.loads(original['messages'][1]['content'])
    if set(value)!={'query','current_context','facts','source_evidence'}:
        raise ValueError('Expected unannotated committed Actor payload')
    sources={'query':value['query'],'current_context':value['current_context'],
        **{f'F{i}':text for i,text in enumerate(value['facts'])}}
    for row in value['source_evidence']:
        if row['memory_id'] in sources:raise ValueError('Evidence ID collision')
        sources[row['memory_id']]=row['text']
    payload={'query':value['query'],'current_context':value['current_context'],
        'fact_sources':[{'source_id':f'F{i}','text':text} for i,text in enumerate(value['facts'])],
        'source_evidence':deepcopy(value['source_evidence'])}
    return value,sources,payload


def request(original):
    _,_,payload=public_payload(original)
    body=deepcopy(original);body.update(max_tokens=8192,
        messages=[{'role':'system','content':BINDER},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}])
    return body


def decode(original,response):
    value,sources,_=public_payload(original);obj=parse_object(response)
    if not isinstance(obj,dict) or set(obj)!={'memory_use_instructions','needs'}:
        raise ValueError('Expected shared use notes and information needs')
    notes=obj['memory_use_instructions']
    if not isinstance(notes,list) or any(not isinstance(n,dict) or set(n)!={'memory_id','use_instruction'} for n in notes):
        raise ValueError('Invalid source-use notes')
    if [n['memory_id'] for n in notes]!=[n['memory_id'] for n in value['source_evidence']]:
        raise ValueError('Cannot add, drop, or reorder committed sources')
    for n in notes:
        text=n['use_instruction']
        if not isinstance(text,str) or not text.strip() or len(text)>700 or len(text.split())>80:
            raise ValueError('Invalid source-use text capacity')
    needs=obj['needs']
    if not isinstance(needs,list) or len(needs)>3:raise ValueError('At most three needs')
    for i,n in enumerate(needs,1):
        if not isinstance(n,dict) or set(n)!={'id','kind','need','anchor','status','evidence'} or n['id']!=f'N{i}':
            raise ValueError('Invalid need identity/fields')
        if n['kind'] not in {'PERSONAL_INFORMATION','TASK_CONDITION'} or n['status'] not in {'DIRECT','RELATED_ONLY','MISSING','GENERAL_INFERENCE'}:
            raise ValueError('Invalid information kind/status')
        for k in ['need','anchor']:
            if not isinstance(n[k],str) or not n[k].strip() or len(n[k])>240:raise ValueError('Invalid need text')
        if len(n['need'].split())>50 or not any(n['anchor'] in value[k] for k in ['query','current_context']):
            raise ValueError('Need not anchored to current task')
        refs=n['evidence']
        if not isinstance(refs,list) or len(refs)>3:raise ValueError('Invalid evidence list')
        if n['status'] in {'DIRECT','RELATED_ONLY'} and not refs:raise ValueError('Support assessment requires evidence')
        if n['status']=='MISSING' and refs:raise ValueError('Missing information cannot have support')
        if n['status']=='GENERAL_INFERENCE' and n['kind']!='TASK_CONDITION':raise ValueError('Cannot infer private detail as general knowledge')
        for ref in refs:
            if not isinstance(ref,dict) or set(ref)!={'source_id','quote'}:raise ValueError('Invalid evidence reference')
            sid,quote=ref['source_id'],ref['quote']
            if not isinstance(sid,str) or sid not in sources or not isinstance(quote,str) or not quote or len(quote)>500 or quote not in sources[sid]:
                raise ValueError('Unknown source or inexact quote')
    return deepcopy(obj)


def actor(original,response,show_status):
    obj=decode(original,response);body=deepcopy(original);payload=json.loads(body['messages'][1]['content'])
    if obj['memory_use_instructions']:payload['memory_use_instructions']=obj['memory_use_instructions']
    contract=[]
    for n in obj['needs']:
        if n['status'] in {'MISSING','RELATED_ONLY'}:
            instruction=('This personal value or relationship is not established by the supplied evidence. '
                'Complete grounded parts and state the gap or ask for needed details; do not invent values, causes or times, '
                'or turn unknown into false/zero/completed.' if n['kind']=='PERSONAL_INFORMATION' else
                'This instance-specific condition is not established. Discuss it conditionally or as something to check; '
                'do not assert that it holds or invent a new goal.')
        elif n['status']=='GENERAL_INFERENCE':
            instruction=('This is a fallible inferred task-success condition, not a new user fact. '
                'Preserve the literal requested outcome and legitimate optional preferences while considering this condition.')
        else:
            instruction=('Consult the cited originals to the extent they support this need. '
                'The support assessment is fallible and creates no additional fact or relationship.')
        contract.append({'information_need':n['need'],'current_task_anchor':n['anchor'],
            'kind':n['kind'],'model_assessed_support':n['status'],
            'evidence_source_ids':list(dict.fromkeys(r['source_id'] for r in n['evidence'])),
            'instruction':instruction})
    if show_status and contract:payload['task_information_contract']=contract
    body['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
    return {'request':body,'binding_audit':{'prediction':obj,'status_visible':show_status,
        'unestablished_personal_needs':[n['id'] for n in obj['needs'] if n['kind']=='PERSONAL_INFORMATION' and n['status'] in {'MISSING','RELATED_ONLY'}],
        'semantic_correctness_proven':False}}
