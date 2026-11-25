"""Official generation checks with a disclosed model/parser adaptation."""
from pathlib import Path
from .adapters import pure_functions

FILES = {'acknow':'check_acknowledge.txt', 'violate':'check_violation.txt',
         'hallucinate':'check_hallucination.txt', 'helpful':'check_helpful.txt'}
SYSTEM = "You are a helpful assistant in evaluating an AI assistant's reponse. You should be fair and strict and follow the user's instruction"


def build_prompt(upstream, metric, reference, answer, checks):
    text = (Path(upstream)/'error_type'/FILES[metric]).read_text()
    if metric == 'acknow':
        replacements = {'end_generation':answer, 'question':reference['question']}
    elif metric in {'violate','helpful'}:
        replacements = {'preference':reference['preference'], 'question':reference['question'], 'end_generation':answer}
    else:
        replacements = {'preference':reference['preference'], 'assistant_restatement':checks['acknow']['extract_pref']}
    for key, value in replacements.items(): text = text.replace('{'+key+'}', value)
    return text


def parse_check(upstream, metric, raw):
    from bs4 import BeautifulSoup
    functions = pure_functions(Path(upstream)/'generation_task/llm_based_evaluation_errortypes.py',
        {'parse_explanation_and_answer', 'parse_preference_and_answer'}, {'BeautifulSoup':BeautifulSoup})
    function = 'parse_preference_and_answer' if metric == 'acknow' else 'parse_explanation_and_answer'
    content, answer = functions[function](raw)
    if answer.lower() not in {'yes','no'}: raise ValueError('Missing or ambiguous PrefEval answer')
    return {'answer':answer, 'extract_pref' if metric == 'acknow' else 'explanation':content}


def aggregate(checks):
    if set(checks) != set(FILES): raise ValueError('Incomplete four-check evaluation')
    for row in checks.values():
        if row.get('answer','').lower() not in {'yes','no'}: raise ValueError('Invalid check')
    ack = checks['acknow']['answer'].lower() == 'yes'
    hallucination = ack and checks['hallucinate']['answer'].lower() == 'yes'
    violation = checks['violate']['answer'].lower() == 'yes'
    unhelpful = checks['helpful']['answer'].lower() == 'no'
    inconsistent = ack and not hallucination and violation and not unhelpful
    hallucinated_violation = ack and hallucination and violation and not unhelpful
    unaware = not ack and violation and not unhelpful
    return {'preference_adherence_accuracy':int(not any([inconsistent,hallucinated_violation,unaware,unhelpful])),
            'acknowledgement':ack,'hallucination':hallucination,'violation':violation,
            'error_unhelpful':unhelpful,'error_inconsistent':inconsistent,
            'hallucination_of_preference_violation':hallucinated_violation,
            'preference_unaware_violation':unaware,
            'protocol':'PrefEval_official_generation_checks_Qwen_variant_v1'}
