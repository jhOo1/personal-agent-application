"""Finalize exact-identity paired AI review; retain every native artifact."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT)]
import run_qamc_rpreasoner_paper as r
from prepare_qamc_rpreasoner_review import identity
from qamc.transport_helpers import atomic_json

# Structured transcription of the six already-completed V1 reads, not new
# model judgments or newly chosen favorable scores. Native values stay intact.
PRIOR_CANDIDATE_BOUNDS = {
    'rpeval/fused/explicit_preference/single/48': [1, 1],
    'rpeval/fused/implicit_preference/single/16': [1, 1],
    'rpeval/fused/explicit_preference/multi/138': [1, 2],
    'rpeval/fused/implicit_preference/multi/111': [1, 1],
    'rpeval/fused/explicit_preference/multi/54': [3, 4],
    'rpeval/official_dev_v2/explicit_preference/multi/119': [2, 2],
}


def main():
    plan = r.read(r.OUT / 'PLAN.json'); r.check(plan)
    terminal = r.read(r.OUT / 'TERMINAL_CHECKPOINT.json')
    assert terminal['process_exit_code_observed'] == 0 and terminal['saved_cells'] == 48
    for path, expected in terminal['outcome_sha256'].items():
        assert r.fh(ROOT / path) == expected
    ledger = r.ledger()
    review_plan = r.read(r.OUT / 'PAIRED_REVIEW_PLAN.json')
    fresh_file = r.OUT / 'FRESH_REVIEW_NOTES_V2.json'
    fresh = r.read(fresh_file)['reviews']
    fresh_map = {(v['uid'], v['method']): v for v in fresh}
    assert len(fresh_map) == len(fresh) == 28
    old_file = r.OUT / 'SOURCE_ANSWER_REVIEW_V1.json'
    old = r.read(old_file)['reviews']
    assert {v['uid'] for v in old} == set(PRIOR_CANDIDATE_BOUNDS)
    bound_pool = defaultdict(list)
    for v in fresh:
        bound_pool[v['identity']].append(v['conditional_ai_bounds'])
    for v in old:
        bound_pool[v['source_reference_view_answer_identity']].append(PRIOR_CANDIDATE_BOUNDS[v['uid']])
    for row in review_plan['rows']:
        for info in row['methods'].values():
            for prior in info['prior_reviews']:
                if prior['conditional_ai_bounds'] is not None:
                    bound_pool[info['identity']].append(prior['conditional_ai_bounds'])
    queue = {v['uid']: v for v in r.read(r.OUT / 'REVIEW_QUEUE.json')['rows']}
    rows, matrix = [], {}
    for row in review_plan['rows']:
        c = r.read(ROOT / queue[row['uid']]['packet'])
        assert r.fh(ROOT / queue[row['uid']]['packet']) == row['packet_sha256']
        methods = {}
        for arm, info in row['methods'].items():
            out = c['candidate'] if arm == 'CANDIDATE' else c['controls'][arm]
            key = identity(c['public_input'], c['evaluation_only_reference'], out)
            assert key == info['identity']
            entry = fresh_map.get((row['uid'], arm))
            if entry:
                assert entry['identity'] == key
                status, note = 'FRESH_COMPLETE_SOURCE_ANSWER_READ', entry['observations']
            else:
                assert info['prior_reviews'], (row['uid'], arm)
                status = 'EXACT_PRIOR_SOURCE_ANSWER_REVIEW_REUSED'
                note = '\n\n'.join(dict.fromkeys(v['observations'] for v in info['prior_reviews']))
                for prior in info['prior_reviews']:
                    assert r.fh(ROOT / prior['source_path']) == prior['source_sha256']
            bounds = bound_pool.get(key, [])
            envelope = [min(v[0] for v in bounds), max(v[1] for v in bounds)] if bounds else None
            methods[arm] = {'identity': key, 'status': status, 'observations': note,
                            'conditional_ai_bounds': envelope, 'prior_reviews': info['prior_reviews'],
                            'human_reviews': 0}
            matrix[row['uid'], arm] = methods[arm]
        rows.append({'uid': row['uid'], 'methods': methods, 'packet_sha256': row['packet_sha256']})
    statuses = Counter(v['status'] for row in rows for v in row['methods'].values())
    assert len(rows) == 21 and sum(statuses.values()) == 84
    result = {'version': 'paired_source_answer_review_v2', 'rows': rows,
              'coverage': {'changed_roots': 21, 'methods_per_root': 4,
                           'fresh_method_reads': statuses['FRESH_COMPLETE_SOURCE_ANSWER_READ'],
                           'exact_method_reuses': statuses['EXACT_PRIOR_SOURCE_ANSWER_REVIEW_REUSED'],
                           'remaining_unreviewed_changed_methods': 0},
              'human_reviews': 0, 'new_model_calls': 0, 'all48_roots_calibrated': False,
              'native_scores_overwritten': False, 'review_is_unblinded_AI': True}
    atomic_json(r.OUT / 'SOURCE_ANSWER_REVIEW_V2.json', result)
    atomic_json(r.OUT / 'REVIEW_COVERAGE_V2.json', result['coverage'])

    # The unchanged roots retain their native values by assumption. Shared
    # answers share the same interval so duplicated outputs cannot create a win.
    native = r.read(r.OUT / 'RESULTS.json')
    atoms = {v['uid']: v for v in native['atomic_rows']}
    details = {v['case']['uid']: v for v in r.read(r.OUT / 'CASE_DETAILS.json')}
    old_atoms = {(v['uid'], v['arm']): v for v in r.read(r.PARENT / 'RPEVAL_AVAILABILITY.json')['rows']}
    for arm, path in [('P0', r.P0 / 'PAIRED_DIAGNOSTIC.json'), ('CF0', r.CF / 'RESULTS.json')]:
        for v in r.read(path)['atomic_rows']:
            old_atoms[v['uid'], arm] = v
    sensitivity = []
    for baseline in plan['baseline_arms']:
        ids = sorted(uid for uid in atoms if old_atoms.get((uid, baseline), {}).get('matched') is not None)
        low = high = 0; per_root = []
        for uid in ids:
            a, b = atoms[uid], old_atoms[uid, baseline]
            bound = lambda arm, value: matrix.get((uid, arm), {}).get('conditional_ai_bounds') or [value, value]
            ab, bb = bound('CANDIDATE', a['matched']), bound(baseline, b['matched'])
            c = details[uid]
            if c['candidate']['answer'] == c['controls'][baseline]['answer']:
                joint = [min(ab[0], bb[0]), max(ab[1], bb[1])]
                ab = bb = joint; delta = [0, 0]
            else:
                delta = [ab[0] - bb[1], ab[1] - bb[0]]
            low += delta[0]; high += delta[1]
            per_root.append({'uid': uid, 'candidate_bounds': ab, 'control_bounds': bb, 'delta_bounds': delta})
        sensitivity.append({'baseline': baseline, 'common_roots': len(ids),
                            'conditional_paired_delta_bounds': [low, high], 'roots': per_root})
    atomic_json(r.OUT / 'AI_SENSITIVITY_V2.json', {'rows': sensitivity, 'new_calls': 0,
                'not_confidence_intervals_or_calibrated_scores': True,
                'assumption': 'Reviewed bounds envelop all structured prior/fresh estimates; unchanged roots keep native match. No favorable endpoint chosen.'})
    text = ['# RPR paired source/answer audit V2\n',
            '21 changed roots ×4 methods covered:28 fresh method reads,56 exact prior review reuses. Human0; no model requests. Other27 roots not newly calibrated. Native scores/failures unchanged.\n',
            '## Conditional paired sensitivity\n']
    for v in sensitivity:
        text.append(f'Against {v["baseline"]}: common{v["common_roots"]}, conditional delta{v["conditional_paired_delta_bounds"]}. Not a confidence interval or corrected benchmark score.\n')
    text += ['\n## First-visible failures and surviving evidence\n',
             'Admissions: mild sports transferred to parents/children, learning added to relaxation, convenience/late work added to health goals, home/challenge/cooking added to a commercial gathering. Both source and query matter.\n',
             'Underuse: vegan-only and ground-only constraints are softened toB; the generator then offers prohibited alternatives. This is a real error beyond Judge ambiguity.\n',
             'Generation: sleep-audio33 has correctAA policies but mentions avoidance of memory topics. Strong-rhythm avoidance is generic sleep advice; finance mention is a source-visibility hypothesis needing a fixed-policy factor, not confirmed causality.\n',
             'Scoring/data: overlap among nature/crowd, challenge, quiet-group/solitude and night-tourism histories inflates some errors. Public child history explicitly permits blocks/drawing while its private summary bans all craft; the strong summary is not a missing public instruction. No native label is rewritten.\n',
             'Do not add a second estimator or a new planner by default. Continue the minimal direct-admission direction, with criterion improvement and controlled presentation tests separated. No SOTA or universal superiority claim.\n']
    for row in rows:
        text += [f'## {row["uid"]}\n']
        for arm, info in row['methods'].items():
            text += [f'### {arm}: {info["status"]}; bounds{info["conditional_ai_bounds"]}\n', info['observations'] + '\n']
    (r.OUT / 'ERROR_ANALYSIS_V2.md').write_text('\n'.join(text).rstrip() + '\n')
    base_package = (r.OUT / 'AI_REVIEW_PACKAGE.md').read_text()
    append = ['\n# New completed paired review V2\n',
              'The earlier package review-gap statements are historical. The new audit below covers all21 changed roots, with explicit reuse; all48 calibration remains false. Native results/costs are unchanged.\n',
              (r.OUT / 'ERROR_ANALYSIS_V2.md').read_text()]
    latest = ('# Latest paired-review status V2\n\nAll21 changed roots now have four-method source/answer review, '
              'using28 fresh reads and56 exact prior-review reuses. Human0. Native scores/calls unchanged. '
              'Earlier review-gap statements in the original package below are historical. '
              'The completed audit and conditional intervals follow that original package.\n\n')
    (r.OUT / 'AI_REVIEW_PACKAGE_V2.md').write_text(latest + base_package.rstrip() + '\n' + '\n'.join(append))
    for path, expected in terminal['outcome_sha256'].items():
        assert r.fh(ROOT / path) == expected
    assert r.ledger() == ledger
    print(json.dumps({'coverage': result['coverage'], 'conditional_sensitivity': [
        {k: v[k] for k in ('baseline', 'common_roots', 'conditional_paired_delta_bounds')} for v in sensitivity],
        'new_calls': 0, 'native_outcomes_unchanged': True}))


if __name__ == '__main__':
    main()
