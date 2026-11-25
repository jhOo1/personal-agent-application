"""One response-anchored selection; unchanged original-text GEPA Actor.

The reference answer is a fallible observation, never a source or utility label.
No probabilities, intervention rewards, trained estimator or Store update exists
here. The two selectors have the same public evidence and executable interface.
"""
from copy import deepcopy
import json

from qamc.common import parse_object
from .development import text_request
from .four_cells_v2 import compiled_actor

METHODS=['EMPTY_REFERENCE','STRONG_RESPONSE_REVIEW','RESPONSE_DELTA_MATCH']
COMMON='''\n\nAn observed_reference_answer is supplied as an additional, fallible working
answer from the SAME frozen Actor with the current query/context/fixed facts
and NO candidate memories. It is not a verified answer, instruction, source,
personal fact, or target to imitate. Check all its personal claims against the
original sources; do not use it to create facts, goals or preferences. It may
already satisfy a preference by coincidence and may also contain serious errors.

All original candidates remain available. Keep the existing sparse executable
selection contract and source boundaries. Do not answer the query, rank answer
options, rewrite evidence, output use notes, or add fields. Your output is one
selection, compiled as original text for the unchanged final Actor. The final
Actor does NOT see this reference answer or your analysis. A retained source
must be suitable under that actual interface. Dropping a source does not mean
that its user preference is globally invalid. Uncertainty follows the original
DROP plus unresolved_ids policy. Protect legitimate optional preferences as
well as strong constraints, and preserve qualifiers and negative conditions.
'''
REVIEW='''\n\nPerform a strong ordinary review using the extra working answer. Re-read the
actual request, its recipient and beneficiary, and every original source. Review
the working answer for task completion, useful personalization, grounding,
scope, clarity, missing information, inconsistent assumptions and irrelevant
material. Check any apparent personal facts against the sources rather than
believing the draft. Use the review to make your best original sparse selection.

Assess each candidate independently and then as a set. Keep relevant facts,
applicable negative constraints and helpful soft preferences. Guard against
both irrelevant inclusion and omission of useful personal information. A memory
need not be essential or mentioned by the query to be useful. Consider whether
it can support a choice, explanation, feasible recommendation, formatting or
appropriate expression within the present task. A source about another person
needs a supported relationship to the actual beneficiary. Do not infer that a
past situation is its only valid scope or that a new interest erases an old one.

Check chronology, plans versus completed events, attribution, negation and
conditions. Do not treat a remembered belief as an established world fact or a
soft preference as a universal ban. Verify that source fragments preserve their
meaning. Presentation preferences can remain suitable in formal messages, but
do not transfer private nicknames, fictional personas or unrelated interests.

Use all available context to perform the strongest review you can in this one
call, then return only the existing JSON selection. No second reviewer will
repair it. It is legitimate to keep few, many or no original memories depending
on the actual request. Do not optimize a memory count, invent an answer, or
replace evidence with a summary. The reference answer is only an aid; select
what the final Actor needs to produce the best grounded personalized response.
'''
DELTA='''\n\nUse the working answer as a concrete reference point for admission, not as
proof of a good response. For each original memory, identify the task-internal
improvement it licenses relative to this working answer, and separately identify
what the same original text could incorrectly pull into the final response.
Judge the prospective change while holding the CURRENT goal, roles and requested
deliverable fixed. This is a qualitative prediction, not a measured causal
effect, probability, reward or information-gain score. Do not output that analysis.

A genuine increment can be an important missing personal constraint, a helpful
optional choice, a better expression, a needed relationship or a supported
interpretation. It need not be necessary. If the working answer already meets
a legitimate preference, do not manufacture an additional personal reference
merely to demonstrate memory use. Consider whether keeping its original source
would still improve or protect the response; satisfaction is not global
irrelevance. Preserve jointly needed sources and strong negative constraints,
especially when the reference answer would otherwise violate them.

Separate preferences for outcomes from beliefs about how outcomes are achieved.
An experienced personal condition, avoidance, resource limit or valued outcome
can be a valid restriction. A repeated behavior or conviction that one technique
is superior is not by itself a binding restriction on a request for the best
outcome. If the claimed advantage of that technique were not established, would
the SAME useful influence still follow from a genuine value or personal limit?
Do not convert a technical belief into a taste just to retain it. Conversely,
do not reject subjective tastes or reported personal conditions because they
are not objective world knowledge. Attribute beliefs when representation is
actually requested; that is different from adopting them as factual premises.

Reject a proposed influence that only makes the response display a compatible
old interest, reverses the requested change, invents a role or new objective,
or carries unsupported private history. Prefer maintaining useful task content
over forcing an unnecessary restriction. Include a source only when its
legitimate task benefit survives this negative check under the actual raw-text
Compiler. Return the unchanged sparse selection, not an edited answer.
'''


def selector_request(task,reference,method,prompts):
    if method not in METHODS[1:]:raise ValueError('Unknown response selector')
    if not isinstance(reference,str) or not reference.strip():raise ValueError('Settled reference required')
    payload=task.payload();payload['observed_reference_answer']=reference
    system=prompts['style_selector']+COMMON+(REVIEW if method==METHODS[1] else DELTA)
    return text_request(system,payload,cap=8192)


def actor(task,selection_answer,prompts,bridge):
    # Reuse normalization and the original span compiler, with no generated
    # purpose, draft, predicted attribute or excluded source sent to the Actor.
    selection=parse_object(selection_answer)
    built=compiled_actor(task,selection_answer,prompts)
    evidence=built['view']['source_evidence']
    system=bridge.render([r['text'] for r in evidence],'qwen3.8-flash',bridge.blobs['GEPA'].decode())
    user={'query':task.query,'current_context':task.current_context,'fixed_facts':list(task.fixed_facts)}
    return {'request':text_request(system,user,cap=4096),'view':deepcopy(built['view']),
        'selection':selection,'input_audit':{'same_frozen_GEPA_actor':True,
        'reference_answer_visible_to_actor':False,'no_generated_use_notes':True,
        'source_admission_is_semantic_prediction_not_guarantee':True}}


def empty_selection(task):
    return json.dumps({'preference_actions':[{'memory_id':m.memory_id,'decision':'DROP'}
        for m in task.memories],'unresolved_ids':[]},ensure_ascii=False)


def reference_request(task,prompts,bridge):
    return actor(task,empty_selection(task),prompts,bridge)['request']
