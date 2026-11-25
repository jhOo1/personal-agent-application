"""Adapted upstream rubric, loaded as literals without executing API code."""
import ast
import math
import re

METRICS = ('OPB', 'UPB', 'RII', 'FM', 'VG', 'Judge')


def load_rubrics(path):
    names = {'LLM_judge_prompt', 'LLM_judge_multiple_prompt'}
    result = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    result[target.id] = ast.literal_eval(node.value)
    if set(result) != names: raise ValueError('Upstream rubric missing')
    return result


def judge_prompt(rubrics, evaluation_row, answer, multiple=False):
    # Called only after generation. This object must never enter selector/Actor.
    label = evaluation_row['intent_type']
    if not multiple:
        label = {'ignore':'忽略偏好', 'support':'支持性偏好', 'supportive':'支持性偏好',
                 'dominate':'以偏好为主线', 'dominant':'以偏好为主线'}.get(label, label)
    return rubrics['LLM_judge_multiple_prompt' if multiple else 'LLM_judge_prompt'].format(
        persona=evaluation_row['persona'], question=evaluation_row['question'], reply=answer,
        intent=evaluation_row.get('intent') or evaluation_row.get('reason'), intent_type=label)


def parse_score(value, preference_count=1, multiple=False):
    # No missing metric, malformed JSON, or bool score becomes a semantic zero.
    for key in METRICS:
        number = value.get(key)
        if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 5:
            raise ValueError('Invalid severity: '+key)
    if multiple:
        match = re.fullmatch(r'(\d+)\s*/\s*(\d+)', str(value.get('match', '')))
        if not match or type(value.get('full_match')) is not bool: raise ValueError('Invalid multi match')
        n, d = map(int, match.groups())
        if d != preference_count or not 0 <= n <= d or value['full_match'] != (n == d):
            raise ValueError('Inconsistent multi denominator')
    else:
        if type(value.get('match')) is not bool: raise ValueError('Invalid single match')
        n, d = int(value['match']), 1
    return {'matched':n, 'total':d, 'severity':{k:value[k] for k in METRICS},
            'protocol':'rpeval_archived_rubric_adapted_v1', 'lower_severity_is_better':True}
