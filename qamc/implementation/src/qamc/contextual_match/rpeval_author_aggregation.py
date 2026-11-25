"""Execute only archived author aggregation functions on saved judge objects.

No author imports, client constructors or inference functions execute. The
executor returns already supplied entries; a model function is a hard error.
The exact author summary and an independently counted component table are kept
separate, including the single-track summary's variable-shadowing behavior.
"""
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
import ast
import io
import json
import os
import re
import tempfile

METRICS = ('OPB', 'UPB', 'RII', 'FM', 'VG', 'Judge')


class _Ready:
    def __init__(self, item):
        self.item = item

    def result(self):
        return self.item


class _ReplayExecutor:
    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def submit(self, unused_model_function, item, *args):
        # Never execute the supplied generation or judge function.
        return _Ready(item)


def _forbidden_model_call(*args, **kwargs):
    raise AssertionError('Offline aggregation cannot invoke a model')


def load_functions(path, multiple):
    tree = ast.parse(Path(path).read_text())
    names = {'run_generation_evaluation'} | ({'_nm_pair', '_to_int_0_5'} if multiple else set())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != names:
        raise ValueError('Archived aggregation function set changed')
    # Compile definitions only. In particular, never execute the module-level
    # imports, sys.path mutation, CLI or provider/client setup.
    namespace = {'re': re, 'json': json, 'os': os, 'datetime': datetime,
        'defaultdict': defaultdict, 'METRIC_KEYS': list(METRICS),
        'ThreadPoolExecutor': _ReplayExecutor, 'as_completed': lambda futures: futures,
        'tqdm': lambda iterable, **kwargs: iterable,
        'evaluate_generated_response': _forbidden_model_call}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def replay(path, entries, multiple):
    if not entries or any(not isinstance(e.get('judge_result'), dict) for e in entries):
        raise ValueError('A finite nonempty list of saved judge objects is required')
    ns = load_functions(path, multiple)
    ns['load_json'] = lambda unused: entries
    with tempfile.TemporaryDirectory(prefix='qamc_author_aggregation_') as directory:
        with redirect_stdout(io.StringIO()):
            ns['run_generation_evaluation']('SAVED_OUTPUTS_NOT_AN_API_INPUT', directory,
                None, None, model_name='SAVED_OUTPUT_REPLAY', prompt_type='offline', max_workers=1)
        summaries = [json.loads(line) for line in (Path(directory)/'gen_summary_log.jsonl').read_text().splitlines()]
        if len(summaries) != 1:
            raise ValueError('Unexpected author summary count')
        summary = summaries[0]
        if json.loads(Path(summary['output_file']).read_text()) != entries:
            raise ValueError('Author replay changed a saved entry')
    # These three fields describe the artificial replay, not a historical model
    # request. Remove them from the score table instead of claiming native runs.
    summary = {k: v for k, v in summary.items() if k not in ('timestamp', 'model', 'output_file', 'prompt_type')}
    sums, counts = Counter(), Counter()
    for entry in entries:
        value = entry['judge_result']
        for metric in METRICS:
            v = ns['_to_int_0_5'](value.get(metric)) if multiple else value.get(metric)
            if isinstance(v, (int, float)):
                sums[metric] += v
                counts[metric] += 1
    intended = {m: sums[m]/counts[m] if counts[m] else None for m in METRICS}
    return {'author_summary': summary,
        'component_counts': {m: counts[m] for m in METRICS},
        'component_sums': {m: sums[m] for m in METRICS},
        'intended_global_means': intended,
        'author_single_summary_differs_from_global': not multiple and summary['avg_scores'] != intended,
        'aggregation_only_not_native_generation': True, 'model_calls': 0,
        'replay_order_is_supplied_order_not_historical_as_completed': True}
