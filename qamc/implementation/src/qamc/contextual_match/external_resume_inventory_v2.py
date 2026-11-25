"""Diagnostic-only separation of proven migration reservations from deliveries."""
from copy import deepcopy


def without_verified_reservations(index, claims, journal_origin):
    """Do not mutate a cache or authorize dispatch; show a counterfactual inventory.

    The caller must first revalidate every claim against the drained migration
    receipt and read-only source journal. Physical failures and any other
    namespace's unknowns are retained even when their request hashes match.
    """
    approved = {c['request_sha256'] for c in claims}
    if len(approved) != len(claims):
        raise ValueError('Migration reservation request identities are ambiguous')
    for c in claims:
        if (c['classification'] != 'MIGRATION_RESERVED_NO_HTTP_RECORD_RECONFIRMED'
                or c['physical_files'] or c['logical_output_exists']
                or c['old_status_preserved'] != 'STARTED_DELIVERY_UNKNOWN'):
            raise ValueError('Claim is not a verified drained reservation')
    output = deepcopy(index)
    removed = []
    output['records'] = []
    for r in index['records']:
        if (r['origin'] == journal_origin and r['body_sha256'] in approved
                and r['request_path'] is None and r['response_path'] is None
                and r['status'] == 'PRIOR_METADATA_ONLY_DELIVERY_UNRESOLVED'):
            removed.append(deepcopy(r))
        else:
            output['records'].append(deepcopy(r))
    return output, {'excluded_only_in_diagnostic_copy': removed,
                    'source_index_modified': False, 'old_journal_modified': False,
                    'physical_failure_reclassified': False, 'dispatch_authorized': False}


def actor_parity(source_rows, baseline_rows):
    """Compare actual public interfaces without assuming author text is JSON."""
    from collections import Counter, defaultdict
    import json
    from qamc.common import sha
    baseline = {r['uid']: r for r in baseline_rows}
    if len(baseline) != len(baseline_rows):
        raise ValueError('Duplicate F00 Actor identity')
    counts, pairs, missing = defaultdict(Counter), [], []
    for row in source_rows:
        if row['uid'] not in baseline:
            raise ValueError('External root absent from fixed v2 panel')
        left, right = row.get('actor_request'), baseline[row['uid']].get('actor_request')
        if not left or not right:
            missing.append({'uid': row['uid'], 'method': row['method'],
                            'external_request_present': bool(left), 'F00_request_present': bool(right)})
            continue
        item = {'uid': row['uid'], 'method': row['method'], 'left_request_sha256': sha(left),
                'F00_request_sha256': sha(right),
                'same_actor_system': left['messages'][0]['content'] == right['messages'][0]['content'],
                'same_decoding_fields': all(left.get(k) == right.get(k)
                    for k in ('model', 'temperature', 'max_tokens', 'stream', 'stream_options')),
                'same_query_field': None}
        try:
            a, b = (json.loads(body['messages'][1]['content']) for body in (left, right))
        except (ValueError, TypeError):
            item['input_shape'] = 'NATIVE_TEXT_INTERFACE_NO_QUERY_FIELD_COMPARISON'
        else:
            if isinstance(a, dict) and isinstance(b, dict):
                item.update(input_shape='JSON_OBJECT', same_query_field=a.get('query') == b.get('query'))
            else:
                item['input_shape'] = 'NON_OBJECT_JSON'
        pairs.append(item)
        for key in ('same_actor_system', 'same_decoding_fields', 'same_query_field'):
            if item[key] is not None:
                counts[row['method']][key+'_compared'] += 1
                counts[row['method']][key+'_equal'] += item[key]
        counts[row['method']]['compiled_pairs'] += 1
    return {'scope': 'Saved external Actor wires vs initial v2 F00, not Window2 same-draft review control',
            'pairs': pairs, 'missing_actor_pairs': missing, 'by_method': {k: dict(v) for k, v in counts.items()},
            'native_text_interface_not_a_parse_failure': True,
            'same_system_does_not_mean_same_all_metadata_or_evidence': True,
            'new_model_calls': 0, 'scores_modified': False, 'goal_complete': False}
