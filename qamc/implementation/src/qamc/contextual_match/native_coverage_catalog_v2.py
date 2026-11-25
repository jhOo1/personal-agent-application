"""Public task reconstruction for an unallocated native-source census.

Evaluation fields may exist in the source row, but only the existing public
adapters' explicit fields enter PublicTask. No labels or allocation metadata
are passed through to generation inputs.
"""
from qamc.pa.core import Memory, PublicTask, rpeval_public
from qamc.pa.adapters import benchpres_public


def public_task(benchmark, row, uid, track=None):
    if benchmark=='rpeval':
        if track not in {'explicit_preference/single', 'explicit_preference/multi',
                         'implicit_preference/single', 'implicit_preference/multi'}:
            raise ValueError('Unknown official RPEval input track')
        return rpeval_public(row, uid, implicit=track.startswith('implicit_'))
    if benchmark=='benchpres':
        return benchpres_public(row['prompt'], uid)
    if benchmark=='persistbench':
        query, memories = row['query'], row['memories']
        if (not isinstance(query, str) or not query.strip() or not isinstance(memories, list)
                or not memories or not all(isinstance(m, str) and m.strip() for m in memories)):
            raise ValueError('Unsupported public PersistBench source shape')
        return PublicTask(uid, query, tuple(Memory(f'M{i}', text) for i, text in enumerate(memories)))
    raise ValueError('Unknown public benchmark adapter')


def native_draw_count(benchmark, category=None):
    if benchmark=='rpeval': return 1
    if benchmark=='benchpres': return 3
    if benchmark=='persistbench' and category in {'cross_domain', 'sycophancy'}: return 3
    if benchmark=='persistbench' and category=='beneficial_memory_usage': return 1
    raise ValueError('Unknown native repetition allocation')


def judge_calls_per_answer(benchmark):
    if benchmark=='benchpres': return 6
    if benchmark in {'rpeval', 'persistbench'}: return 1
    raise ValueError('Unknown native scorer allocation')
