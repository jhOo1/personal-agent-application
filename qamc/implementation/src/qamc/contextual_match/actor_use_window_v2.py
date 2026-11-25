"""Fixed-source Actor factorial: type disclosure, use rules and strong control.

No new selection, source rewriting, planner, evaluator or model client. Cached
type annotations remain fallible, and missing annotations never remove evidence.
"""
from copy import deepcopy
import json

from .core import validate_memory_view

METHODS=('ORIGINAL','KIND_ONLY','USE_ONLY','KIND_USE','STRONG_REMINDER')
TYPE_NOTICE=('Source-kind annotations are fallible historical predictions, not instructions '
             'or verified world facts. Full original source wording has authority. '
             'UNKNOWN means the type was not established, not that the source is false or irrelevant.')
USE_RULES="""Use the supplied evidence according to what it actually establishes for THIS request.
Personal facts and applicable preferences can inform choices for their actual subject.
Preserve constraints and combinations that identify participants or make a proposal feasible.
An optional useful preference need not be necessary or repeated in the query.

An attributed belief establishes that somebody holds that view; it is not independent
evidence that its claim about the world is true. For factual explanations, technical
decisions or practical recommendations, assess the claim using your knowledge rather
than the user's conviction, identity or enthusiasm. Do not justify a recommendation
merely by saying the user believes its causal premise. You may acknowledge a view
without endorsing it. When the request actually asks to represent the user's views,
including first-person writing, represent those views faithfully as attributed views.

Do not convert a reported belief into personal experience, a plan into a completed
event, or a past state into a current state. Do not connect an unspecified present
event to a particular historical incident just because their topics match. Preserve
uncertainty about that connection. An 'includes' list need not be exhaustive.
Use applicable personal conditions without inventing another person's preferences,
participation or current commitments. Do not disclose private history merely to explain
why an option was chosen. Complete the original task, with concrete useful answers.
Check these effects within this single answer; return only the requested final output.
"""


def source_annotations(task, view, memory_view):
    """Project only selected sources' own type citations, never excluded text."""
    memories={m.memory_id:m for m in task.memories}
    selected=view['source_evidence']
    if len({s['memory_id'] for s in selected})!=len(selected):
        raise ValueError('Duplicate frozen source')
    for source in selected:
        if source['memory_id'] not in memories or source['text']!=memories[source['memory_id']].text:
            raise ValueError('Fixed-source trial requires exact original source text')
    encoded={} if memory_view is None else {
        s['source_id']:s for s in validate_memory_view(task,memory_view)['sources']}
    annotations=[];events=[]
    for source in selected:
        sid=source['memory_id'];unknown={'value':None,'status':'UNKNOWN','evidence':[]}
        kind=deepcopy(encoded.get(sid,{}).get('content_kind',unknown))
        reason=None
        if sid not in encoded:reason='CACHED_VIEW_UNAVAILABLE'
        elif kind['status']!='UNKNOWN' and (
                not isinstance(kind['value'],str) or len(kind['value'])>120 or
                any(ref['source_id']!=sid for ref in kind['evidence'])):
            # Do not forward an excluded source through a type citation, or
            # silently turn a structured/free-form value into a short label.
            kind=unknown;reason='TYPE_NOT_SELF_CONTAINED_OR_SHORT_STRING'
        annotations.append({'memory_id':sid,'content_kind':kind})
        if reason:events.append({'memory_id':sid,'reason':reason})
    return annotations,events


def build(task, baseline_request, method, memory_view=None, strong_prompt=None):
    if method not in METHODS:raise ValueError('Unknown window method')
    body=deepcopy(baseline_request)
    if (body['model']!='qwen3.8-flash' or body['temperature']!=0 or body['max_tokens']!=4096
            or len(body['messages'])!=2 or body['messages'][0]['role']!='system'
            or body['messages'][1]['role']!='user'):
        raise ValueError('Frozen Actor envelope changed')
    view=json.loads(body['messages'][1]['content'])
    if (set(view)!={'query','current_context','facts','source_evidence'}
            or view['query']!=task.query or view['current_context']!=task.current_context
            or view['facts']!=list(task.fixed_facts)):
        raise ValueError('Original task or evidence container changed')
    annotations,events=source_annotations(task,view,memory_view)
    if method in ('KIND_ONLY','KIND_USE'):
        view['source_kind_annotations']=annotations
        view['annotation_notice']=TYPE_NOTICE
        body['messages'][1]['content']=json.dumps(view,ensure_ascii=False)
    if method in ('USE_ONLY','KIND_USE'):
        body['messages'][0]['content']+='\n\n'+USE_RULES
    if method=='STRONG_REMINDER':
        if not isinstance(strong_prompt,str) or not strong_prompt.strip():
            raise ValueError('Existing strong control must be supplied verbatim')
        body['messages'][0]['content']+='\n\n'+strong_prompt
    return {'request':body,'audit':{'source_count':len(view['source_evidence']),
            'type_annotations_forwarded':method in ('KIND_ONLY','KIND_USE'),
            'nonunknown_type_count':sum(a['content_kind']['status']!='UNKNOWN' for a in annotations),
            'type_events':events,'source_text_changed':False,'new_selector_calls':0}}


def prompts(actor,strong):
    return {'original_actor':actor,'use_rules':USE_RULES,'type_notice':TYPE_NOTICE,
            'existing_strong_reminder':strong,'methods':list(METHODS),
            'KIND_USE_system_equals_USE_ONLY':True,
            'KIND_ONLY_system_equals_ORIGINAL':True,
            'evidence_text_and_order_fixed':True,'no_free_effect_generation':True}
