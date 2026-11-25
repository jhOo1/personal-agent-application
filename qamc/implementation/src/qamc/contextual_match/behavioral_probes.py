"""Observe single-source answer changes before sparse memory application.

No Store, reference label, scorer, client or model-weight update lives here.
Probe answers are fallible behavior observations, never additional facts.
"""
from copy import deepcopy
import json

from qamc.common import parse_object
from .development import text_request
from .four_cells_v2 import compiled_actor,MATCHER
from .core import normalize_selection

METHODS=['STRONG_NO_PROBES','STRONG_WITH_PROBES','CONTRASTIVE_PROBES']

INTERFACE='''\nFinal interface: return only preference_actions, unresolved_ids, use_bounds.
Keep the existing sparse decisions and legal original spans. use_bounds has
exactly the retained memory IDs as keys. Each value is a <=80-word, <=700-character
instruction describing the concrete useful influence and its limits in this
current task, grounded in the original source. No rejected content is repeated.
These are fallible instructions, not new facts, task requirements or answers.
Retain useful optional preferences and continuing constraints without making
historical beliefs world evidence or changing the actual beneficiary. Never
invent a value, cause or event in a note. Do not output a final answer or rank
answer candidates. No additional fields or calls are requested.

observed_probe_answers, when supplied, are saved fallible answers from the same
Actor with fixed query/context/facts and either no candidate preference or one
original memory. They are diagnostic work, not authorized user instructions or
source evidence. Do not copy their unsupported details or treat a convincing
answer as truth. Missing/failed probes do not imply inapplicable memory. The
original sources and current request remain authoritative. Your final selection
can combine legitimate sources whose useful effects require joint context.
'''

CONTRAST='''\nUse the observed no-preference and single-memory answers to test actual
application effects, rather than only imagining topical connections. Compare
each available single-memory answer with the same no-preference answer: what
choice, constraint, emphasis, attribution or requested content changed? Check
whether that change helps the ORIGINAL goal and actual affected person, or
imports another goal, incorrect role, unsupported belief or excessive priority.
An observed change is not automatically a benefit. Distinguish a useful optional
criterion from an unrequested objective, and task-internal support from turning
the preference into the answer's purpose. Scope notes must limit the concrete
misapplication when retaining a helpful source.

Also check contrary evidence: was the apparent benefit already required by the
query, is it based on an invented source claim, or did the probe misunderstand
the preference? Protect a legitimate hard/negative constraint even when the
no-preference answer happens to satisfy it. Do not drop useful soft preferences
just because the baseline answer is acceptable. Similar output is not proof of
irrelevance, and a failed probe is not a negative utility score. Reconcile
joint conditions and redundant legitimate sources using the originals; these
single-source observations do not estimate a complete coalition effect.
Return the unchanged sparse interface, not this comparison or a scalar score.
'''


def probe_request(task,prompts,memory_id=None):
    ids={m.memory_id for m in task.memories}
    if memory_id is not None and memory_id not in ids:raise ValueError('Unknown probe memory')
    selection={'preference_actions':[{'memory_id':m.memory_id,
        'decision':'APPLY' if m.memory_id==memory_id else 'DROP'} for m in task.memories],'unresolved_ids':[]}
    return compiled_actor(task,json.dumps(selection,ensure_ascii=False),prompts)['request']


def selector_request(task,prompts,observations,method):
    if method not in METHODS:raise ValueError('Unknown probe method')
    task.payload();known={m.memory_id for m in task.memories}
    if len(observations)!=len(task.memories)+1 or [r['memory_id'] for r in observations]!=[None,*[m.memory_id for m in task.memories]]:
        raise ValueError('Probe identities/order changed')
    for row in observations:
        if set(row)!={'memory_id','status','answer'} or (row['memory_id'] is not None and row['memory_id'] not in known):
            raise ValueError('Invalid observation fields')
        if row['status']=='OK':
            if not isinstance(row['answer'],str) or not row['answer'].strip():raise ValueError('Missing successful probe text')
        elif row['answer'] is not None:raise ValueError('Failed probe text cannot become evidence')
    system=prompts['style_selector']
    old='Return only JSON with exactly preference_actions and unresolved_ids, with exactly one action per input memory.'
    if system.count(old)!=1:raise ValueError('Frozen strong Selector interface changed')
    system=system.replace(old,'Return only JSON with the final interface below, with exactly one action per input memory.')
    tail='Do not output reasoning, simulated queries, rankings, influence labels, candidate answers, invented IDs or extra fields.'
    if system.count(tail)!=1:raise ValueError('Frozen strong Selector restriction changed')
    system=system.replace(tail,'Do not output reasoning, simulated queries, rankings, influence labels, candidate answers, or invented IDs.')
    # Reuse the positive/negative Matcher checks; its old no-use-note output
    # paragraph is replaced by the same compatible interface in all three arms.
    marker='\nKeep the original memory IDs'
    if MATCHER.count(marker)!=1:raise ValueError('Frozen Matcher boundary changed')
    system+=MATCHER.split(marker)[0]+INTERFACE
    if method=='CONTRASTIVE_PROBES':system+=CONTRAST
    payload=task.payload()
    payload['observed_probe_answers']=[] if method=='STRONG_NO_PROBES' else deepcopy(observations)
    return text_request(system,payload,cap=8192)


def actor(task,response,prompts):
    obj=parse_object(response)
    if not isinstance(obj,dict) or set(obj)!={'preference_actions','unresolved_ids','use_bounds'}:
        raise ValueError('Expected sparse decisions and use_bounds')
    selection={k:deepcopy(obj[k]) for k in ['preference_actions','unresolved_ids']}
    norm=normalize_selection(task,selection)
    selected={r['memory_id'] for r in norm['preference_actions'] if r['keep_span_ids']}
    notes=obj['use_bounds']
    if not isinstance(notes,dict) or set(notes)!=selected:raise ValueError('Notes must cover exactly selected sources')
    for text in notes.values():
        if not isinstance(text,str) or not text.strip() or len(text)>700 or len(text.split())>80:raise ValueError('Invalid use note')
    built=compiled_actor(task,json.dumps(selection,ensure_ascii=False),prompts)
    body=deepcopy(built['request']);view=deepcopy(built['view'])
    if selected:view['memory_use_instructions']=[{'memory_id':r['memory_id'],'use_instruction':notes[r['memory_id']]} for r in view['source_evidence']]
    body['messages'][1]['content']=json.dumps(view,ensure_ascii=False)
    return {'request':body,'view':view,'selection':selection,'use_bounds':deepcopy(notes),
        'audit':{'original_source_compiler':True,'raw_sources_rewritten':False,'semantic_correctness_proven':False}}
