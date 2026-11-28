"""Validate offline-generated instruction edits before using them on the joint fit panel."""
import json
import re

from qamc.common import parse_object, sha

MODES = ('scope_of_influence','realize_applicable_preference')
_ID = re.compile(r'(?i)\b(?:benchpres|rpeval|persistbench|uid|gold label|(?:implicit|explicit)/\d+|[0-9a-f]{8,})\b')
_WORDS = re.compile(r'\w+|[^\s\w]',re.UNICODE)
MAX_POLICY_CHARS = 1300


def corpus_ngrams(feedback, len_words=8):
    forbidden = set()

    def append(text):
        tokens = _WORDS.findall(text.casefold())
        forbidden.update(tuple(tokens[i:i+len_words]) for i in range(len(tokens)-len_words+1))

    for examples in feedback['examples'].values():
        for case in examples:
            for value in case['task'].values():
                append(json.dumps(value,ensure_ascii=False) if not isinstance(value,str) else value)
            for source in case['history']:
                append(source['text'])
            append(case['parent_answer'])
            append(case['comparison_answer'])
    return forbidden


def validate(content, feedback):
    proposal=parse_object(content)
    if not isinstance(proposal,dict) or set(proposal)!=set(MODES):
        raise ValueError('Expected one instruction for each of the two mutation targets')
    forbidden=corpus_ngrams(feedback)
    accepted={}
    for mode in MODES:
        instruction=proposal[mode]
        if not isinstance(instruction,str) or not 45<=len(instruction.strip())<=MAX_POLICY_CHARS:
            raise ValueError('Instruction must be nonempty and fit the frozen character budget')
        if _ID.search(instruction):
            raise ValueError('Instruction contains a benchmark identifier or case-specific marker')
        tokens=_WORDS.findall(instruction.casefold())
        if any(tuple(tokens[i:i+8]) in forbidden for i in range(len(tokens)-7)):
            raise ValueError('Instruction copies offline example text')
        accepted[mode]=instruction.strip()
    if accepted[MODES[0]]==accepted[MODES[1]]:
        raise ValueError('Both mutation targets produced the same instruction')
    return accepted


def instruction_packet(feedback, current_policy):
    """Summarize private traces for proposal generation only."""
    cases=[]
    for candidates in feedback['examples'].values():
        for ex in candidates:
            cases.append(dict(purpose=ex['purpose'],task=ex['task'],history=ex['history'],
                 current=ex['parent_answer'],alternative=ex['comparison_answer'],
                 score_delta=ex.get('delta'),current_rating=ex.get('parent_rating'),
                 alternative_rating=ex.get('comparison_rating'),
                 prior_flags=ex.get('known_score_flags')))
    return {'current_instruction':current_policy,'offline_contrasts':cases}


def candidate_hash(parent, policy, target):
    return sha({'parent':parent,'instruction':policy,'target':target})
