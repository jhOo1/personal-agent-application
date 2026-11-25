"""Evaluation-only usage annotation without author target labels or method IDs."""
from qamc.common import parse_object
from .development import text_request

SYSTEM='''Annotate visible preference use in the supplied completed answer.
You are NOT given the desired utilization labels, method name or selected-memory
set. Do not infer them. Do not judge the author's target, answer correctness or
whether historical memory actually caused a phrase; judge only visible alignment.

For EACH memory in its supplied order, classify observed use:
A: its content is absent or does not affect the answer's choices, restrictions,
emphasis or expression. Ordinary words shared with a source are not automatically
use of that source. B: it is used as a supporting optional consideration, without
being the main organizing objective or an overriding restriction. C: it strongly
organizes/dominates the answer or is treated as a required constraint.
Distinguish weak source mention from an implemented recommendation. Consider the
actual query when deciding whether a criterion dominates or is merely supportive.
Do not assume every memory must appear. Do not output what the desired labels
should be, a score, a recommendation, or reasoning.

Return only {"observed":[{"memory_id":"M0","usage":"A|B|C","quote":null}]}.
There must be exactly one row per supplied memory ID. For A, quote must be null.
For B/C, quote must be a nonempty EXACT substring of the supplied ANSWER (not a
memory quote), at most500characters, supporting the classification. No extra keys.
'''


def request(query,memories,answer):
    if not isinstance(query,str) or not isinstance(answer,str) or not answer.strip():raise ValueError('Missing observation input')
    if not isinstance(memories,list) or not memories or any(not isinstance(t,str) for t in memories):raise ValueError('Invalid memory list')
    return text_request(SYSTEM,{'query':query,'memories':[{'memory_id':f'M{i}','text':t} for i,t in enumerate(memories)],'answer':answer},cap=8192)


def parse(raw,memories,answer):
    obj=parse_object(raw);expected={f'M{i}' for i in range(len(memories))}
    if not isinstance(obj,dict) or set(obj)!={'observed'} or not isinstance(obj['observed'],list):raise ValueError('Invalid observation envelope')
    seen={}
    for row in obj['observed']:
        if not isinstance(row,dict) or set(row)!={'memory_id','usage','quote'}:raise ValueError('Invalid observation row')
        mid,usage,quote=row['memory_id'],row['usage'],row['quote']
        if mid not in expected or mid in seen or usage not in {'A','B','C'}:raise ValueError('Unknown/duplicate preference or usage')
        if usage=='A':
            if quote is not None:raise ValueError('Absent usage needs null quote')
        elif not isinstance(quote,str) or not quote.strip() or len(quote)>500 or quote not in answer:raise ValueError('Usage evidence not quoted from answer')
        seen[mid]=row
    if set(seen)!=expected:raise ValueError('Missing preference annotation')
    return {'observed_policy':''.join(seen[f'M{i}']['usage'] for i in range(len(memories))),
        'rows':[seen[f'M{i}'] for i in range(len(memories))],
        'historical_causality_proven':False,'human_annotation':False}
