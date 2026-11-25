"""Pinned Inspect Judge prompts/parsing without executing provider or CLI code."""
import ast
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import cast


COMMIT = '50b8b19c3d4765898fa2f35d125389be45af9c3c'
KINDS = {
    'FAILURE_TYPE_CROSS_DOMAIN': 'cross_domain',
    'FAILURE_TYPE_SYCOPHANCY': 'sycophancy',
    'FAILURE_TYPE_BENEFICIAL_MEMORY': 'beneficial_memory_usage',
}
PROMPTS = {
    'JUDGE_SYSTEM_PROMPT_SINGLE_CROSS_DOMAIN',
    'JUDGE_SYSTEM_PROMPT_SINGLE_SYCOPHANCY',
    'JUDGE_SYSTEM_PROMPT_SINGLE_POSITIVE_MEMORY',
}


def pure_functions(tree, names, namespace):
    """Compile only fixed, source-hashed definitions; never top-level imports."""
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise ValueError('Pinned pure Judge interface changed')
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    exec(compile(module, COMMIT+':pure_judge_functions', 'exec'), namespace)


class InspectPersistJudge:
    def __init__(self, root, lock):
        if lock['author_commit'] != COMMIT:
            raise ValueError('Different Inspect version')
        trees = {}
        for asset in lock['assets']:
            path = (Path(root)/asset['file']).resolve()
            if not path.is_relative_to(Path(root).resolve()):
                raise ValueError('Judge source escapes repository')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != asset['sha256'] or len(raw) != asset['bytes']:
                raise ValueError('Pinned Inspect source changed')
            trees[path.name] = ast.parse(raw.decode('utf-8'))
        if set(trees) != {'prompts.py', 'utils.py', 'scorers.py', 'persistbench.py'}:
            raise ValueError('Incomplete Inspect source assets')
        prompt_tree = trees['prompts.py']
        values = {n.targets[0].id: ast.literal_eval(n.value) for n in prompt_tree.body
                  if isinstance(n, ast.Assign) and len(n.targets) == 1
                  and isinstance(n.targets[0], ast.Name) and n.targets[0].id in PROMPTS}
        if set(values) != PROMPTS:
            raise ValueError('Missing native Judge prompt')
        configs = [n.value for n in prompt_tree.body if isinstance(n, ast.AnnAssign)
                   and isinstance(n.target, ast.Name) and n.target.id == 'JUDGE_CONFIGS']
        if len(configs) != 1 or not isinstance(configs[0], ast.Dict):
            raise ValueError('Native category mapping changed')
        self.configs = {}
        for key, value in zip(configs[0].keys, configs[0].values, strict=True):
            if (not isinstance(key, ast.Name) or key.id not in KINDS
                    or not isinstance(value, ast.Call) or value.args
                    or not isinstance(value.func, ast.Name) or value.func.id != 'JudgeConfig'):
                raise ValueError('Unexpected native category configuration')
            fields = {}
            for keyword in value.keywords:
                if keyword.arg == 'system_prompt':
                    if not isinstance(keyword.value, ast.Name) or keyword.value.id not in values:
                        raise ValueError('Native prompt reference changed')
                    fields[keyword.arg] = values[keyword.value.id]
                else:
                    fields[keyword.arg] = ast.literal_eval(keyword.value)
            if set(fields) != {'system_prompt', 'score_field', 'min_score', 'max_score'}:
                raise ValueError('Native Judge fields changed')
            self.configs[KINDS[key.id]] = SimpleNamespace(**fields)
        if set(self.configs) != set(KINDS.values()):
            raise ValueError('Native categories incomplete')
        namespace = {'json': json, 're': re, 'cast': cast}
        pure_functions(prompt_tree, {'formatted_memories', 'build_judge_prompt'}, namespace)
        pure_functions(trees['utils.py'], {'_parse_json_object', 'extract_json_from_response'}, namespace)
        pure_functions(trees['scorers.py'], {'_parse_judge_json'}, namespace)
        self.functions = namespace

    def request(self, memories, query, answer, category, model, cap=8192):
        if (category not in self.configs or model not in {'kimi-k2-thinking', 'qwen3.8-flash'}
                or not isinstance(answer, str) or not answer.strip()):
            raise ValueError('Explicit category/model and a real saved answer required')
        return {'model': model, 'messages': [
            {'role': 'system', 'content': self.configs[category].system_prompt},
            {'role': 'user', 'content': self.functions['build_judge_prompt'](memories, query, answer)}],
            'temperature': 0, 'max_tokens': cap, 'stream': True,
            'stream_options': {'include_usage': True}}

    def parse(self, category, text):
        config = self.configs[category]
        rating, reason, original = self.functions['_parse_judge_json'](text, config)
        value = original[config.score_field]
        # Preserve the author's int conversion. Flag its permissiveness rather
        # than silently changing old/native scoring to a stricter new rubric.
        return {'rating': rating, 'reasoning': reason, 'original_json': original,
                'native_parser_boolean_or_fractional_coercion':
                    type(value) is bool or isinstance(value, float) and not value.is_integer(),
                'native_provider_parity_proven': False}


def fallback_eligible(receipts):
    """Only explicit unsupported-route responses authorize this fallback.

    Stream interruption, missing completion, throttling, quota, and length are
    not proof that a model is unsupported. Unknown deliveries are never resent.
    """
    return bool(receipts) and all(
        r.get('status') == 'HTTP_ERROR' and r.get('http_status') in {400, 404, 405, 410, 422, 501}
        for r in receipts)
