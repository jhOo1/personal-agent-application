"""Audit saved public dispatch records without sending or repairing requests."""
from collections import Counter
from proposals.qamc_protocol_alignment.sampling import sampling_key


def audit_records(records, allowed_keys, now):
    keys = []
    for r in records:
        key = sampling_key(r['unit'])
        if key not in allowed_keys:
            raise ValueError('Physical request outside frozen new-call allocation')
        if r.get('automatic_retries') != 0:
            raise ValueError('Unexpected automatic retry')
        if not isinstance(r.get('started_unix'), (int, float)):
            raise ValueError('Missing saved start time')
        if r['status'] not in ('OK', 'FAILED_DELIVERY_UNKNOWN', 'KNOWN_LENGTH_FAILURE', 'HTTP_ERROR', 'PENDING_DELIVERY_UNKNOWN'):
            raise ValueError('Unknown physical status')
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise ValueError('Repeated physical sampling identity')
    if len(records) > len(allowed_keys):
        raise ValueError('Frozen new-call upper bound exceeded')
    ordered = sorted(records, key=lambda r: r['started_unix'])
    intervals = [b['started_unix']-a['started_unix'] for a, b in zip(ordered, ordered[1:])]
    faults = []
    for r in records:
        if r['status'] != 'FAILED_DELIVERY_UNKNOWN':
            continue
        duration = r.get('elapsed_seconds')
        if not isinstance(duration, (int, float)) or duration < 0:
            raise ValueError('Terminal stream failure has no valid elapsed time')
        end = r['started_unix']+duration
        later = [x for x in ordered if x['started_unix'] >= end and sampling_key(x['unit']) != sampling_key(r['unit'])]
        first = later[0] if later else None
        gap = first['started_unix']-end if first else None
        faults.append({'unit': r['unit'], 'request_sha256': r['request_sha256'], 'error': r.get('error'),
                       'estimated_terminal_utc': end, 'first_later_unit': first['unit'] if first else None,
                       'first_later_saved_start_gap_seconds': gap,
                       'saved_gap_at_least_300_seconds': gap >= 300 if gap is not None else None,
                       'no_later_request_observed_yet': first is None,
                       'not_proof_of_network_timing_or_delivery': True})
    unknown_usage = sum(r.get('usage') is None for r in records if r['status'] != 'PENDING_DELIVERY_UNKNOWN')
    return {'physical_records': len(records), 'frozen_new_call_upper_bound': len(allowed_keys),
            'statuses': dict(Counter(r['status'] for r in records)), 'duplicate_physical_sampling_identities': 0,
            'saved_records_have_zero_automatic_retries': True, 'terminal_unknown_usage': unknown_usage,
            'minimum_saved_start_interval_seconds': min(intervals) if intervals else None,
            'saved_start_intervals_below_nominal_3_1': sum(v < 3.1 for v in intervals),
            'faults': faults, 'observed_at_utc': now, 'non_atomic_live_snapshot': True,
            'delivery_or_grammar_failure_not_a_semantic_error': True,
            'full_network_spacing_compliance_proven': False, 'new_model_calls': 0}
