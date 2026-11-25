"""Question/label-blind normalization of public historical source identifiers."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import re


def opaque_history_case(case):
    result=deepcopy(case)
    if case['benchmark']!='longmemeval':return result,{}
    sessions={};turns={};ordinal=Counter()
    for turn in result['history']:
        old_session=turn['session_id'];old_id=turn['id']
        if old_session not in sessions:sessions[old_session]=f'S{len(sessions)+1:06d}'
        ordinal[old_session]+=1
        turn['session_id']=sessions[old_session]
        turn['id']=f'{turn["session_id"]}:T{ordinal[old_session]:04d}'
        if old_id in turns:raise ValueError('duplicate historical source ID')
        turns[old_id]=turn['id']
    return result,{'sessions':sessions,'turns':turns}


def validate_opaque_histories(cases):
    for case in cases:
        if case['benchmark']!='longmemeval':continue
        sessions={};seen=set();ordinal=Counter()
        for turn in case['history']:
            sid=turn['session_id']
            if not re.fullmatch(r'S\d{6}',sid):raise ValueError('nonopaque public session identifier')
            if sid not in sessions:sessions[sid]=f'S{len(sessions)+1:06d}'
            if sessions[sid]!=sid:raise ValueError('opaque session order changed')
            ordinal[sid]+=1
            if turn['id']!=f'{sid}:T{ordinal[sid]:04d}' or turn['id'] in seen:raise ValueError('nonopaque or duplicate public turn identifier')
            seen.add(turn['id'])
