"""Exercise released PersistBench control rendering and repeat allocation offline."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json

import qamc_contextual_match_v2_persist_authors as archived
from qamc.common import sha
from qamc.contextual_match import gepa_unified
from qamc.contextual_match.native_coverage_catalog_v2 import public_task
from qamc.contextual_match.native_judging import REPEATS
from qamc.contextual_match.native_repeats import build_manifest
from qamc.transport_helpers import atomic_json
from proposals.qamc_protocol_alignment.sampling import sampling_key

ROOT, read = archived.ROOT, archived.read
BASE = archived.OUT.parent
OUT = BASE / 'persist_formal_author_replay_v1'
CATALOG = BASE / 'native_full_coverage_catalog_v1/CURRENT.json'
SOURCE = ROOT / 'literature/qamc_pa_v1/PersistBench/benchmark_samples/full_benchmark.jsonl'
METHODS = ['PB_FULL', 'PB_GEPA', 'PB_RUBRIC', 'PB_NO_MEMORY']


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def replay():
    previous = read(archived.OUT / 'PLAN.json')
    archived.check(previous, False)
    bridge = archived.PersistAuthorBridge(archived.parent.persist.UP)
    metadata = sorted((r for r in read(CATALOG)['rows'] if r['benchmark'] == 'persistbench'),
                      key=lambda r: r['row_index'])
    if ([r['row_index'] for r in metadata] != list(range(500))
            or {r['source_file'] for r in metadata} != {str(SOURCE.relative_to(ROOT))}
            or {r['source_sha256'] for r in metadata} != {digest(SOURCE)}):
        raise ValueError('Official source identity or coverage differs')
    native = [json.loads(line) for line in SOURCE.read_text().splitlines()]
    if len(native) != len(metadata):
        raise ValueError('Unexpected source row count')
    protocol = {
        'namespace': 'persist_formal_author_replay_preview_only',
        'model': previous['protocols']['qwen']['model'], 'concurrency': 8,
        'spacing_seconds': 3.2, 'repeat_policy': REPEATS,
        'stages': {'Actor': previous['protocols']['qwen']['stages']['Actor']},
    }
    waves = sorted((archived.OUT / 'waves').glob('*.json'))
    history = {(r['uid'], r['method']): r for p in waves for r in read(p)['rows']}
    old = {r['line']-1: r for r in previous['cases']}
    rows = []
    identities = set()
    history_status = Counter()
    for case, item in zip(metadata, native, strict=True):
        task = public_task('persistbench', item, case['uid'])
        category = case['category']
        if sha(task.payload()) != case['public_input_sha256'] or item['failure_type'] != category:
            raise ValueError('Common source or category changed')
        if case['native_final_draws_per_method'] != REPEATS[category]:
            raise ValueError('Catalogue and independent repeat count disagree')
        bodies = {m: bridge.actor(task, m, '')['request'] for m in METHODS}
        if bodies['PB_GEPA'] != gepa_unified.actor(task, bridge)['request']:
            raise ValueError('GEPA reference wire differs from the shared baseline')
        per_draw = {task.uid: {m: {i: b for i in range(REPEATS[category])} for m, b in bodies.items()}}
        manifest = build_manifest([{'uid': task.uid, 'category': category}],
                                  per_draw, METHODS, protocol, 'Actor')
        keys = {sampling_key(j['unit']) for j in manifest['units']}
        if len(keys) != len(manifest['units']) or keys & identities:
            raise ValueError('Duplicate independent sampling identity')
        identities.update(keys)
        validated = {}
        if case['row_index'] in old:
            old_case = old[case['row_index']]
            for m, body in bodies.items():
                saved = history[old_case['uid'], m]
                if saved['actor_request'] != body or saved['actor_request_sha256'] != sha(body):
                    raise ValueError('Old author-control request drifted')
                status = saved['actor_status']
                if status == 'OK' and not saved.get('answer'):
                    raise ValueError('Old successful trajectory lost its answer')
                history_status[status] += 1
                validated[m] = {'old_actor_status': status, 'answer_sha256': sha(saved['answer'])
                                if saved.get('answer') else None}
        rows.append({'uid': task.uid, 'source_catalog_id': case['catalog_id'], 'row_index': case['row_index'],
                     'category': category, 'group_id': case['analysis_group_id'],
                     'common_input_sha256': case['public_input_sha256'],
                     'illustrative_sampling_assignments': manifest['assignments'],
                     'verified_old_single_draws': validated})
    counts = Counter(r['category'] for r in rows)
    if counts != Counter({'cross_domain': 200, 'sycophancy': 200, 'beneficial_memory_usage': 100}):
        raise ValueError('Source population no longer matches the released categories')
    pins = [Path(__file__).resolve(), SOURCE, CATALOG, archived.OUT / 'PLAN.json', *waves]
    return {
        'official_roots': len(rows), 'category_counts': dict(counts), 'method_order': METHODS,
        'source_groups': len({r['group_id'] for r in rows}), 'actor_protocol_preview': protocol,
        'logical_draws': sum(len(r['illustrative_sampling_assignments']) for r in rows),
        'unique_sample_positions': len(identities), 'old_request_statuses': dict(history_status),
        'old_draws_included_as_replicates': 0, 'dispatch_plan_created': False,
        'public_task_text_or_judge_labels_exported': False, 'new_model_calls': 0,
        'author_source_lock': bridge.manifest(),
        'source_pins': {str(p.relative_to(ROOT)): digest(p) for p in pins}, 'rows': rows,
    }


if __name__ == '__main__':
    result = replay()
    atomic_json(OUT / 'PUBLIC_REQUEST_REPLAY.json', result)
    print({k: result[k] for k in ('official_roots', 'category_counts', 'source_groups',
                                 'logical_draws', 'unique_sample_positions', 'old_request_statuses',
                                 'new_model_calls')})
