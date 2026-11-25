"""RP-Reasoner Appendix C multi-preference, zero-shot template adaptation.

Figures 15-17 supply distinct estimators and a policy-aware generator. The paper
does not supply the concrete examples represented by its Example placeholders.
Those blocks are omitted explicitly, not replaced with benchmark demonstrations.
This adapter never reads evaluation labels, scores or the original persona
summary hidden behind an implicit dialogue. It is not a literal few-shot replay.
"""
from pathlib import Path
import json
import re

from qamc.common import parse_object
from proposals.qamc_rpreasoner_paper.engine import aggregate

ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = ROOT/'proposals/qamc_rpreasoner_paper/appendix_prompts_v1.json'
METHOD = 'RPR_APPENDIX_ZERO_SHOT_MULTI'


def templates():
    return json.loads(PROMPT_PATH.read_text())['templates']


def public_inputs(task):
    # Appendix templates here are only validated for the existing RPEval multi
    # panel. Reject nonempty auxiliary channels rather than silently lose facts.
    if len(task.memories) < 2 or task.current_context or task.fixed_facts:
        raise ValueError('Appendix multi adapter requires a multi-memory task without extra channels')
    task.payload()
    return {'PERSONAS': json.dumps([m.text for m in task.memories], ensure_ascii=False),
            'QUESTION': task.query}


def render(template, fields):
    # One-pass substitution prevents a literal marker in source text from being
    # interpreted as another formatting instruction. Output-JSON braces survive.
    keys = set(re.findall(r'\{(PERSONAS|QUESTION|INTENTS)\}', template))
    if not keys <= set(fields):
        raise ValueError('Missing template input')
    return re.sub(r'\{(PERSONAS|QUESTION|INTENTS)\}', lambda m: fields[m[1]], template)


def body(content, maximum):
    # Preserve the released client default system message and temperature. Stream
    # receipts and explicit caps use this project's established safe transport.
    return {'model': 'qwen3.8-flash', 'temperature': 0, 'max_tokens': maximum,
            'stream': True, 'stream_options': {'include_usage': True},
            'messages': [{'role': 'system', 'content': 'You are a helpful assistant'},
                         {'role': 'user', 'content': content}]}


def estimator_requests(task):
    fields = public_inputs(task)
    return {stage: body(render(templates()[stage], fields), 8192)
            for stage in ('MLE', 'IPE')}


def rankings(task, raw):
    value = parse_object(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or not isinstance(value.get('ranking'), str):
        raise ValueError('Missing paper ranking string')
    orders = [x.strip().upper() for x in value['ranking'].split('|')]
    if len(orders) != len(task.memories) or any(len(x) != 3 or set(x) != set('ABC') for x in orders):
        raise ValueError('Incomplete ABC permutations; no default or repair')
    # The paper aggregates rankings, not the estimator's redundant policy field.
    # Retain its public raw response separately, including any disagreement.
    return {'rankings': [{'memory_id': m.memory_id, 'order': order}
                         for m, order in zip(task.memories, orders)]}


def generator_request(task, mle, ipe):
    fields = public_inputs(task)
    result = aggregate(task, rankings(task, mle), rankings(task, ipe))
    policy = ''.join(row['policy'] for row in result)
    fields['INTENTS'] = policy
    return {'aggregation': result, 'predicted_policy': policy,
            'view': {'query': task.query, 'current_context': task.current_context,
                     'facts': list(task.fixed_facts),
                     'source_evidence': [{'memory_id': m.memory_id, 'text': m.text}
                                         for m in task.memories],
                     'preference_use_policy': [{'memory_id': row['memory_id'], 'policy': row['policy']}
                                               for row in result]},
            'request': body(render(templates()['Actor'], fields), 4096)}
