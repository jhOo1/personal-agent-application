"""Reported usage versus requested caps, without inventing cap semantics.

Pure evaluation code. A reported completion count above max_tokens is an
observation, not proof that a visible-output or total-generation cap failed.
"""
from collections import defaultdict


def count(value):
    return type(value) is int and value >= 0


def summarize(records):
    seen = set(); groups = defaultdict(list)
    for row in records:
        key = row['physical_record']
        if key in seen:
            raise ValueError('Duplicate physical receipt cannot inflate usage')
        seen.add(key)
        if type(row['requested_cap']) is not int or row['requested_cap'] <= 0:
            raise ValueError('Explicit requested positive cap required')
        groups[(row['model'], row['stage'])].append(row)
    tables = []
    for (model, stage), rows in sorted(groups.items()):
        known = [r for r in rows if count((r.get('usage') or {}).get('completion_tokens'))]
        exceeded = [r for r in known if r['usage']['completion_tokens'] > r['requested_cap']]
        complete_usage = [r for r in rows if all(count((r.get('usage') or {}).get(k))
                          for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'))]
        arithmetic = [r for r in complete_usage if r['usage']['total_tokens'] !=
                      r['usage']['prompt_tokens'] + r['usage']['completion_tokens']]
        tables.append({'model': model, 'stage': stage, 'physical_records': len(rows),
            'pending_records': sum(r['status'] == 'PENDING_DELIVERY_UNKNOWN' for r in rows),
            'completion_usage_known': len(known), 'completion_usage_unknown_or_invalid': len(rows)-len(known),
            'reported_completion_above_requested_cap': len(exceeded),
            'above_cap_by_status': {s: sum(r['status'] == s for r in exceeded)
                                   for s in sorted({r['status'] for r in exceeded})},
            'max_reported_completion_to_requested_cap': max(
                (r['usage']['completion_tokens']/r['requested_cap'] for r in known), default=None),
            'reported_completion_sum_known': sum(r['usage']['completion_tokens'] for r in known) if known else None,
            'reported_total_sum_complete_usage': sum(r['usage']['total_tokens'] for r in complete_usage) if complete_usage else None,
            'complete_usage_records': len(complete_usage), 'arithmetic_mismatch_records': len(arithmetic)})
    return {'tables': tables, 'physical_records': len(records),
        'completion_usage_known': sum(t['completion_usage_known'] for t in tables),
        'reported_completion_above_requested_cap': sum(t['reported_completion_above_requested_cap'] for t in tables),
        'requested_cap_semantics': 'UNVERIFIED_VISIBLE_OUTPUT_VS_TOTAL_GENERATION',
        'above_cap_proves_server_violation': False,
        'actual_model_tokenizer_verified': False,
        'provider_reported_tokens_are_currency_bill': False,
        'hidden_reasoning_recovered': False,
        'old_usage_recalculated_or_replaced': False}
