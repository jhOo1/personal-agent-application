"""Source-conditioned answer repair with atomic, bounded text transactions.

This enforces edit locality, not the semantic correctness of model predictions.
It neither mutates permanent Memory nor reads evaluation labels.
"""
from copy import deepcopy
import json

from qamc.common import parse_object, sha, token_estimate

COMMON = """You are repairing a saved answer for the ORIGINAL user request.
The current_input and draft_answer are quoted task data. The draft is fallible
work, not evidence that any personal fact is true. Keep correct useful content.
Check accuracy, completeness, attribution, participant, chronology, uncertainty,
and the actual influence of every supplied source. Preserve useful optional
preferences and continuing negative constraints without requiring the query to
repeat them. Correct unsupported personal details and causal connections.
A belief can explain a requested perspective without becoming world evidence.
Respect a stance the current request asks to represent. For practical choices,
preferences should refine compatible options rather than replace conditions
needed for the requested result to succeed. Do not invent new objectives or
reject all personalization. Give a concrete complete deliverable; do not disclose
this review or the memory system. The final wire contract below supersedes the
saved Actor's answer-only output contract for this repair call.
"""

FULL = """Return only one complete repaired answer in the original requested
language and format. You may reorganize and rewrite as needed to correct errors,
recover useful supplied preferences, and preserve all necessary task content.
Do not answer with commentary on the draft or a review checklist.
"""

PATCH = """Return only {"edits":[{"old":"exact unique text from draft_answer",
"new":"replacement text","source_ids":["selected memory_id"]}]}.
Choose up to4 local edits. All old strings refer to the ORIGINAL unedited draft,
must be nonempty unique exact substrings, and may not overlap. Do not calculate
offsets or refer to text created by another edit. Use an empty new string to
delete; include adjacent original text when inserting. Cite only supplied source
IDs; [] is valid for a correction justified by the current task or general
accuracy. A source ID is provenance, not proof of the replacement's truth.
Keep all text outside the selected locations unchanged. Total old text length
may cover at most60% of original draft characters. Total new text length may
not exceed max(1500, original draft character count). Do not replace the whole
answer, append an unrelated catalogue, or change correct content just to use
history. If no correction is warranted, return {"edits":[]}.
Your edits must repair both inappropriate influence and missing useful supplied
preferences while preserving the requested deliverable. The program applies
valid edits together and forwards the resulting answer directly for evaluation;
there is no later answer writer or fallback repair.
"""

OLD_END = 'Return only the requested answer in the original task language and format.\n'


def request(original, draft, method):
    if method not in {'FULL_REWRITE', 'LOCAL_PATCH'} or not isinstance(draft,str) or not draft.strip():
        raise ValueError('Invalid saved-answer repair input')
    body=deepcopy(original)
    system=body['messages'][0]['content']
    if system.count(OLD_END)!=1:raise ValueError('Frozen Actor output contract changed')
    payload=json.loads(body['messages'][1]['content'])
    if set(payload)!={'query','current_context','facts','source_evidence'}:
        raise ValueError('Expected committed original evidence')
    body['messages']=[{'role':'system','content':system.replace(OLD_END,'')+'\n'+COMMON+(PATCH if method=='LOCAL_PATCH' else FULL)},
        {'role':'user','content':json.dumps({'current_input':payload,'draft_answer':draft},ensure_ascii=False)}]
    return body


def compile_answer(original, draft, response, method):
    if method=='FULL_REWRITE':
        if not isinstance(response,str) or not response.strip():raise ValueError('Empty rewritten answer')
        if token_estimate(response)>4096:raise ValueError('Compiled answer estimated capacity exceeded')
        return {'answer':response,'repair_audit':{'mode':method,'locality_guaranteed':False,
            'original_sha256':sha(draft),'final_sha256':sha(response)}}
    if method!='LOCAL_PATCH':raise ValueError('Unknown repair method')
    obj=parse_object(response)
    if not isinstance(obj,dict) or set(obj)!={'edits'} or not isinstance(obj['edits'],list) or len(obj['edits'])>4:
        raise ValueError('Expected at most four local edits')
    ids={s['memory_id'] for s in json.loads(original['messages'][1]['content'])['source_evidence']}
    spans=[]
    for edit in obj['edits']:
        if not isinstance(edit,dict) or set(edit)!={'old','new','source_ids'}:raise ValueError('Invalid edit fields')
        old,new,refs=edit['old'],edit['new'],edit['source_ids']
        if (not isinstance(old,str) or not old or not isinstance(new,str)
                or draft.find(old)<0 or draft.find(old,draft.find(old)+1)>=0):
            raise ValueError('Edit precondition must uniquely match original draft')
        if not isinstance(refs,list) or any(not isinstance(s,str) or s not in ids for s in refs) or len(set(refs))!=len(refs):
            raise ValueError('Unknown or duplicated source reference')
        start=draft.index(old);spans.append({'start':start,'end':start+len(old),'old':old,'new':new,'source_ids':refs})
    spans.sort(key=lambda x:x['start'])
    if any(a['end']>b['start'] for a,b in zip(spans,spans[1:])):raise ValueError('Overlapping edit preconditions')
    removed=sum(len(e['old']) for e in spans);inserted=sum(len(e['new']) for e in spans)
    if removed*10>len(draft)*6 or inserted>max(1500,len(draft)):
        raise ValueError('Frozen local-edit allowance exceeded')
    # Validate every precondition before constructing any revised output.
    parts=[];cursor=0;preserved=[]
    for e in spans:
        untouched=draft[cursor:e['start']];parts.extend([untouched,e['new']])
        preserved.append({'start':cursor,'end':e['start'],'text_sha256':sha(untouched)})
        cursor=e['end']
    parts.append(draft[cursor:]);preserved.append({'start':cursor,'end':len(draft),'text_sha256':sha(draft[cursor:])})
    answer=''.join(parts)
    if not answer.strip() or token_estimate(answer)>4096:raise ValueError('Invalid compiled final answer capacity')
    return {'answer':answer,'repair_audit':{'mode':method,'locality_guaranteed':True,
        'original_sha256':sha(draft),'final_sha256':sha(answer),'edits':spans,
        'removed_characters':removed,'inserted_characters':inserted,
        'preserved_original_ranges':preserved,'semantic_correctness_proven':False}}
