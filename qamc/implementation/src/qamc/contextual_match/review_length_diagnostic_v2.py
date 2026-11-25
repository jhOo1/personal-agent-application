"""Post-hoc descriptive answer shape; never a semantic or promotion score."""
from difflib import SequenceMatcher
from statistics import mean, median
from .answer_use_review_v2 import REVIEW_METHODS
from .evaluation import unique_index


def available(row):
    return row is not None and row.get('actor_status') == 'OK' and isinstance(row.get('answer'), str) and bool(row['answer'].strip())


def describe(rows, cases, drafts):
    index = unique_index(rows)
    known = {c['uid']: c for c in cases}
    if any(uid not in known for uid, _ in index): raise ValueError('Unknown length diagnostic root')
    measures = []
    for (uid, method), row in index.items():
        if method not in REVIEW_METHODS or not available(row): continue
        text = row['answer']; draft = drafts[uid].get('draft_answer')
        if not isinstance(draft, str) or not draft.strip(): raise ValueError('Review answer has no saved draft')
        measures.append({'uid': uid, 'benchmark': known[uid]['benchmark'], 'method': method,
                         'mode': row['input_audit']['mode'], 'unicode_codepoints': len(text),
                         'whitespace_units': len(text.split()), 'draft_whitespace_units': len(draft.split()),
                         'same_visible_text_as_draft': text == draft,
                         'line_sequence_similarity_to_draft': SequenceMatcher(None, draft.splitlines(), text.splitlines(), autojunk=False).ratio(),
                         'has_valid_main_score': row.get('score') is not None})
    by_key = {(x['uid'], x['method']): x for x in measures}
    summaries = []
    for benchmark in ('rpeval', 'benchpres', 'persistbench'):
        for method in REVIEW_METHODS:
            measured = [x for x in measures if x['benchmark'] == benchmark and x['method'] == method]
            real = [x for x in measured if x['mode'] == 'ONE_REVIEW_OF_FIXED_ORIGINAL_DRAFT']
            summaries.append({'benchmark': benchmark, 'method': method, 'available_answer_roots': len(measured),
                              'real_review_answer_roots': len(real),
                              'cached_identity_roots': sum(x['mode'] == 'EMPTY_EVIDENCE_BASELINE_IDENTITY' for x in measured),
                              'mean_whitespace_units_real_review': mean(x['whitespace_units'] for x in real) if real else None,
                              'median_whitespace_units_real_review': median(x['whitespace_units'] for x in real) if real else None,
                              'exact_draft_preserved_real_review': sum(x['same_visible_text_as_draft'] for x in real)})
    pairs = []
    for normal, compact in (('GENERIC_REVIEW', 'GENERIC_REVIEW_COMPACT'), ('USE_REVIEW', 'USE_REVIEW_COMPACT')):
        for benchmark in ('rpeval', 'benchpres', 'persistbench'):
            changes = []
            for c in cases:
                if c['benchmark'] != benchmark: continue
                a, b = by_key.get((c['uid'], normal)), by_key.get((c['uid'], compact))
                if not a or not b or any(x['mode'] != 'ONE_REVIEW_OF_FIXED_ORIGINAL_DRAFT' for x in (a, b)): continue
                changes.append({'uid': c['uid'], 'group_id': c.get('analysis_group_id', c['group_id']),
                                'normal_whitespace_units': a['whitespace_units'], 'compact_whitespace_units': b['whitespace_units'],
                                'compact_minus_normal': b['whitespace_units']-a['whitespace_units'],
                                'normal_codepoints': a['unicode_codepoints'], 'compact_codepoints': b['unicode_codepoints'],
                                'codepoint_delta': b['unicode_codepoints']-a['unicode_codepoints'],
                                'compact_to_normal_codepoint_ratio': b['unicode_codepoints']/a['unicode_codepoints'],
                                'compact_to_normal_ratio': b['whitespace_units']/a['whitespace_units']})
            pairs.append({'benchmark': benchmark, 'normal': normal, 'compact': compact, 'common_real_review_roots': len(changes),
                          'shorter_roots': sum(x['compact_minus_normal'] < 0 for x in changes),
                          'longer_roots': sum(x['compact_minus_normal'] > 0 for x in changes),
                          'equal_length_roots': sum(x['compact_minus_normal'] == 0 for x in changes),
                          'codepoint_shorter_roots': sum(x['codepoint_delta'] < 0 for x in changes),
                          'codepoint_longer_roots': sum(x['codepoint_delta'] > 0 for x in changes),
                          'codepoint_equal_roots': sum(x['codepoint_delta'] == 0 for x in changes),
                          'median_compact_to_normal_codepoint_ratio': median(x['compact_to_normal_codepoint_ratio'] for x in changes) if changes else None,
                          'median_compact_to_normal_ratio': median(x['compact_to_normal_ratio'] for x in changes) if changes else None,
                          'changes': changes})
    return {'scope': 'Post-hoc descriptive shape of saved final answers; not a registered efficacy endpoint',
            'rows': measures, 'by_benchmark_method': summaries, 'normal_vs_compact_paired': pairs,
            'whitespace_units_are_not_model_tokens_or_language_invariant_word_counts': True,
            'unicode_codepoints_also_reported_for_unsegmented_languages': True,
            'codepoint_counts_are_not_model_tokens_or_information_content': True,
            'line_similarity_is_not_semantic_preservation_or_bias_measurement': True,
            'cached_identity_excluded_from_actual_compaction_comparison': True,
            'all_answer_available_includes_judge_failures_not_imputed_scores': True,
            'pair_sets_are_not_necessarily_four_arm_or_primary_score_sets': True,
            'source_verified_condition_coverage_not_inferred': True, 'new_model_calls': 0, 'scores_modified': False}
