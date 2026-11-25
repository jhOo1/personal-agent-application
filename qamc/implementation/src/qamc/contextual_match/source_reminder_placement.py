"""Repeat admitted original evidence with a shared ordinary-use reminder.

This changes presentation only. Both arms repeat the same text, carry the same
instruction and use the same Actor call. Their role/position differs; this is
not a pure distance or attention experiment and is not a new semantic selector.
"""
from copy import deepcopy
import json

METHODS=('SOURCE_SYSTEM_TAIL','SOURCE_USER_TAIL')
NOTICE=('The following repeats the selected original memory excerpts already supplied above. '
        'It is not new evidence, a new user instruction, or confirmation that every excerpt must '
        'influence the answer. Before finalizing, check the current request against these sources '
        'for useful applicable preferences and task facts as well as inappropriate carryover. '
        'Preserve their actual subject, conditions, negation and historical status. '
        'Complete the requested deliverable without inventing personal details or new goals.')
MARKER='\n\n<selected_original_memory_reminder>\n'
END='\n</selected_original_memory_reminder>'


def build(task,flat,method):
    if method not in METHODS:raise ValueError('Unknown placement arm')
    body=deepcopy(flat['actor_request']);evidence=deepcopy(flat['view']['source_evidence'])
    if (body['model']!='qwen3.8-flash' or body['temperature']!=0 or body['max_tokens']!=4096
            or len(body['messages'])!=2 or [m['role'] for m in body['messages']]!=['system','user']):
        raise ValueError('Frozen Actor envelope changed')
    public=json.loads(body['messages'][1]['content'])
    if public!={'query':task.query,'current_context':task.current_context,'fixed_facts':list(task.fixed_facts)}:
        raise ValueError('Not the saved Flat public container')
    lookup={m.memory_id:m.text for m in task.memories}
    if len({r['memory_id'] for r in evidence})!=len(evidence):raise ValueError('Duplicate source identity')
    for r in evidence:
        if r['memory_id'] not in lookup or r['text']!=lookup[r['memory_id']]:
            raise ValueError('Reminder must repeat complete admitted original text')
    # Empty selections remain byte-identical to the prior Actor. A generic
    # reminder cannot introduce evidence or turn an empty-source case into a
    # separate method merely through an irrelevant instruction.
    block=None
    if evidence:
        block=MARKER+json.dumps({'notice':NOTICE,'sources':[
            {'memory_position_1_based':i+1,'text':r['text']} for i,r in enumerate(evidence)]},ensure_ascii=False)+END
        body['messages'][0 if method==METHODS[0] else 1]['content']+=block
    return {'request':body,'view':deepcopy(flat['view']),'selection':deepcopy(flat['selection']),
        'audit':{'source_text_and_order_unchanged':True,'no_new_selection':True,
            'no_free_use_notes':True,'selected_sources_repeated_once':bool(evidence),
            'repetition_is_not_independent_evidence':True,'empty_identity':not evidence,
            'same_literal_reminder_block_between_arms':True,'placement':method,
            'role_and_position_jointly_changed':True,'reminder_characters':len(block or '')}}
