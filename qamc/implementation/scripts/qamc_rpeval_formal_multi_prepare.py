"""Freeze official multi coverage without generating or judging new answers.

The existing six policies stay fixed. Preserve legacy identities for24 comparable
roots, and keep all single-preference reserved identities outside this scope.
"""
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
import json

import qamc_rpr_per_persona_run as previous
from qamc.pa.core import rpeval_public

ROOT, read, frozen, pin = previous.ROOT, previous.read, previous.frozen, previous.pin
OUT = previous.spec.BASE/'rpeval_formal_multi_coverage_v1'
CENSUS = previous.spec.BASE/'independent_test_set_preparation_v1'
SOURCE = ROOT/'literature/qamc_pa_v1/RPEval/benchmark_dataset'


def source_key(path, index):
    value = str(path).split('benchmark_dataset/')[-1]
    return value, index


def build():
    previous.check(previous.prepare(), False)
    old = previous.parent.prepare()
    old_cases = {c['uid']: c for c in old['cases']}
    witnesses = read(previous.parent.OUT/'EVALUATION_SOURCE_CENSUS.json')['rows']
    legacy = {source_key(r['source_file'], r['zero_based_row']): r for r in witnesses
              if r['benchmark'] == 'rpeval' and '/multi_testset.json' in r['source_file']}
    native = {source_key(r['source_file'], r['row_index']): r
        for r in read(CENSUS/'CENSUS.json')['catalog']
        if r['benchmark'] == 'rpeval' and r['population'] == 'official' and r['track'].endswith('/multi')}
    if len(legacy) != 24 or len(native) != 300:
        raise ValueError('Official multi identities or legacy membership changed')
    reserved_rows = read(CENSUS/'RESERVED_IDENTITIES.json')['native_cases']
    reserved = {r['source_id'] for r in reserved_rows}
    reserved_groups = {r['audit_group_id'] for r in reserved_rows}
    groups_old = {r['uid']: r['analysis_group_id']
                  for r in read(previous.parent.OUT/'ANALYSIS_GROUPS.json')['rows']}
    union = {r['audit_group_id']: r['audit_group_id'] for r in native.values()}

    def find(group):
        while union[group] != group:
            group = union[group]
        return group

    # Never split a previously conservative source group when expanding scope.
    old_members = defaultdict(list)
    for key, witness in legacy.items():
        old_members[groups_old[witness['uid']]].append(native[key]['audit_group_id'])
    for values in old_members.values():
        root = min(find(v) for v in values)
        for value in values:
            union[find(value)] = root
    cases, public, inherited = [], {}, []
    for setting in ('explicit', 'implicit'):
        path = SOURCE/(setting+'_preference')/'multi_testset.json'
        data = read(path)
        if len(data) != 150:
            raise ValueError('Expected original150 multi rows per memory setting')
        expected_hashes = {w['source_file_sha256'] for w in legacy.values()
                           if source_key(w['source_file'], 0)[0] == source_key(path, 0)[0]}
        if expected_hashes != {pin(path)}:
            raise ValueError('Released source file changed')
        for index, row in enumerate(data):
            key = source_key(path, index)
            identity = native[key]
            if identity['source_id'] in reserved:
                raise ValueError('Reserved confirmation identity overlaps formal multi coverage')
            if identity['audit_group_id'] in reserved_groups:
                raise ValueError('Reserved source group overlaps formal multi coverage')
            prior = legacy.get(key)
            uid = prior['uid'] if prior else f'rpeval/formal_multi_v1/{setting}/{index:03d}'
            task = rpeval_public(row, uid, implicit=setting == 'implicit')
            task.payload()
            if prior:
                if previous.sha(row) != prior['native_row_sha256']:
                    raise ValueError('Legacy native row changed')
                if asdict(task) != asdict(previous.parent.task_for(old_cases[uid])):
                    raise ValueError('Legacy public input differs; cannot re-generate as comparable')
                inherited.append({'uid': uid, 'source_id': identity['source_id'],
                    'public_sha256': previous.sha(task.payload()), 'identity_and_public_input_unchanged': True})
            # Evaluation references are separate from every PublicTask and input.
            evaluation = OUT/'evaluation_only'/f'{setting}_{index:03d}.json'
            frozen(evaluation, row)
            cases.append({'uid': uid, 'benchmark': 'rpeval', 'track': setting+'/multi',
                'source_id': identity['source_id'], 'source_file': str(path.relative_to(ROOT)),
                'row_index': index, 'native_row_sha256': previous.sha(row),
                'evaluation_path': str(evaluation.relative_to(ROOT)),
                'evaluation_hash': previous.spec.prior.parent.legacy.grading.ext.digest(row),
                'analysis_group_id': find(identity['audit_group_id']),
                'census_group_id': identity['audit_group_id'],
                'legacy_same_configuration_uid': uid if prior else None,
                'independent_confirmation': False})
            public[uid] = asdict(task)
    if len(cases) != 300 or len(public) != 300:
        raise ValueError('Duplicate official identities')
    frozen(OUT/'MANIFEST_300.json', cases)
    frozen(OUT/'PUBLIC_TASKS.json', public)
    frozen(OUT/'LEGACY_PUBLIC_INPUT_INHERITANCE.json', inherited)
    summary = {'official_multi_roots': len(cases), 'tracks': dict(Counter(c['track'] for c in cases)),
        'source_groups': len({c['analysis_group_id'] for c in cases}),
        'census_groups_before_old_group_union': len({c['census_group_id'] for c in cases}),
        'legacy_roots_with_unchanged_inputs': len(inherited),
        'reserved_native_identity_overlap': 0, 'reserved_source_group_overlap_rows': 0,
        'new_single_tasks_read_or_dispatched': 0,
        'new_Writer_or_Store_requests': 0, 'new_retrieval_requests': 0, 'new_model_calls': 0,
        'memory_count_histogram': dict(sorted(Counter(len(t['memories']) for t in public.values()).items())),
        'methods': list(previous.parent.METHODS), 'same_common_version_per_method': True,
        'not_an_independent_confirmation': True, 'not_full600_rpeval_or_three_benchmarks': True,
        'nominal_cold_request_positions': 5700,
        'nominal_formula': '300*(C5:2+Gate:2+GEPA:1+MemAdapter:3+RPR:3+Des2Gen:2+sixJudges:6)',
        'actual_new_request_cap_not_finalized': True,
        'model_dispatch_ready': False, 'runner_not_yet_implemented': True,
        'must_inherit_completed_successes_and_failures_without_rerun': True}
    frozen(OUT/'DATA_ACCEPTANCE.json', summary)
    files = [Path(__file__), ROOT/'tests/test_qamc_formal_multi_prepare.py',
        ROOT/'src/qamc/pa/core.py', SOURCE/'explicit_preference/multi_testset.json',
        SOURCE/'implicit_preference/multi_testset.json', CENSUS/'CENSUS.json',
        CENSUS/'RESERVED_IDENTITIES.json', previous.parent.OUT/'PLAN.json',
        previous.parent.OUT/'EVALUATION_SOURCE_CENSUS.json', OUT/'MANIFEST_300.json',
        OUT/'PUBLIC_TASKS.json', OUT/'LEGACY_PUBLIC_INPUT_INHERITANCE.json', OUT/'DATA_ACCEPTANCE.json']
    files.extend(ROOT/c['evaluation_path'] for c in cases)
    frozen(OUT/'FROZEN_DATA.json', {'files': {str(p.relative_to(ROOT)): pin(p) for p in files},
        'maximum_new_physical_requests_for_this_prepare': 0, 'model_dispatch_ready': False,
        'frozen_policy_parent': str((previous.parent.OUT/'PLAN.json').relative_to(ROOT)),
        'all_six_policy_builders_must_remain_frozen_for_formal_run': True})
    return cases, public, summary


if __name__ == '__main__':
    print(json.dumps(build()[2]))
