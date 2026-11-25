"""Window 2: review actual draft use, crossed with an answer-length contract."""
from copy import deepcopy
import json
from .empty_evidence_identity_v2 import payload, empty_evidence

METHODS=('ORIGINAL','STRONG_REMINDER','GUARDED_USE_CACHE_CONTROL',
         'GENERIC_REVIEW','USE_REVIEW','GENERIC_REVIEW_COMPACT','USE_REVIEW_COMPACT')
REVIEW_METHODS=METHODS[3:]
SHARED='''You are revising a saved draft for the user's original request.
The current_input contains the ORIGINAL query, context, facts and selected original
memory excerpts. The draft_answer is fallible work, not an additional factual source.
Return one complete final answer in the user's requested language and format.
Keep correct, useful material; do not change it merely to look different. Do not expose
this review, the memory system, or a checklist. Do not answer with comments on the draft.
'''
GENERIC='''Review the draft thoroughly for accuracy, relevance, completeness, clarity and
correct use of the supplied evidence. Correct unsupported assertions, wrong attribution,
inappropriate personalization, contradictions and omissions. Preserve useful applicable
preferences, negative constraints, uncertainty, subject and chronology. Respect the
actual request rather than adding new goals. Use your knowledge where needed without
inventing personal facts or treating the draft's unsupported claims as evidence.
'''
USAGE='''Review how the draft actually uses the supplied history, not merely whether a
source sounds related. For each consequential claim or choice, internally distinguish:
- a fact or condition about the actual participant;
- a useful preference or negative constraint that shapes that participant's options;
- a viewpoint to represent because the current request asks for that viewpoint;
- an assertion about how the external world works.
Keep legitimate personal facts, optional useful preferences and joint conditions for
the right participant. A preference need not be repeated in the query to be useful.
An attributed belief establishes that someone holds it, not that its external premise
is true. For practical advice and factual/technical claims, check whether the draft
turns conviction into a factual premise or a categorical exclusion. Correct that use
without reflexively disagreeing, banning beliefs, or deleting legal personalization.
If the user explicitly requests writing from a viewpoint, represent it faithfully as
a viewpoint; do not replace the requested thesis with an unrelated task.
Do not promote an old state to a current event, a plan to an accomplishment, a user's
preference to another person's requirement, or a nonexhaustive list to a known total.
Remove unsupported connections and unrelated influence while retaining concrete task
completion and every applicable limiting condition. Do not add private-history
explanations merely to justify choices. Check the revised answer for missing useful
preferences as well as inappropriate carryover. Output only the complete final answer.
'''
COMPACT='''Keep the requested deliverable complete, but remove repeated explanations,
redundant catalogues, near-duplicate variants and generic instructions that do not
help this request. Give a direct answer with a few high-value options unless the user
requests broad coverage or a detailed artifact. Never shorten away necessary facts,
negative constraints, exceptions, uncertainty or jointly required conditions.
'''


def build(original_request, draft_answer, method):
    if method not in REVIEW_METHODS:raise ValueError('Unknown review method')
    if original_request is None or not isinstance(draft_answer,str) or not draft_answer.strip():
        return {'request':None,'mode':'SAVED_DRAFT_UNAVAILABLE'}
    view=payload(original_request)
    if empty_evidence(view):
        return {'request':deepcopy(original_request),'mode':'EMPTY_EVIDENCE_BASELINE_IDENTITY'}
    body=deepcopy(original_request)
    body['messages'][0]['content']+='\n\n'+SHARED+'\n'+(USAGE if method.startswith('USE_') else GENERIC)
    if method.endswith('_COMPACT'):body['messages'][0]['content']+='\n'+COMPACT
    body['messages'][1]['content']=json.dumps({'current_input':view,'draft_answer':draft_answer},ensure_ascii=False)
    return {'request':body,'mode':'ONE_REVIEW_OF_FIXED_ORIGINAL_DRAFT'}


def prompts():
    return {'shared':SHARED,'generic_review':GENERIC,'use_review':USAGE,'compact_contract':COMPACT,
            'methods':list(METHODS),'no_new_selector_or_store':True,
            'same_saved_original_draft_and_evidence':True,'cold_nonempty_calls':2,
            'review_calls_per_nonempty_case':1,'empty_cases_identity_all_four':True}
