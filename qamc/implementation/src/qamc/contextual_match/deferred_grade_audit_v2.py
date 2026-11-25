"""Classify deferred grades without retrying, mutating or choosing scores."""
from collections import Counter
from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key,validate_public_request


def audit_deferred(plan,manifests,outputs,records,expected_jobs,reservations=None):
    reservations=reservations or {}
    allowed=set(plan['allowed_unit_keys']);roots={c['uid'] for c in plan['cases']}
    jobs={};owners={}
    for path,manifest in manifests.items():
        if manifest['status']!='UNISSUED':raise ValueError('Unexpected deferred declaration')
        for job in manifest['jobs']:
            unit,body=job['unit'],job['request'];key=sampling_key(unit)
            validate_public_request(body)
            if (key not in allowed or unit['root_id'] not in roots or unit['method'] not in plan['methods']
                    or unit['stage'] not in ('PersistJudge','RPEvalJudge') or unit['replicate']!=0):
                raise ValueError('Deferred identity outside allocation')
            protocol=plan['protocols']['gpt41'];stage=protocol['stages'][unit['stage']]
            if (unit['protocol_sha256']!=sha(protocol) or body['model']!=protocol['model']
                    or body['temperature']!=stage['temperature'] or body['max_tokens']!=stage['max_tokens']):
                raise ValueError('Deferred protocol changed')
            if key in jobs and jobs[key]!=job:raise ValueError('Deferred identity has conflicting requests')
            jobs[key]=job;owners.setdefault(key,[]).append(path)
    results=[]
    for key,job in sorted(jobs.items()):
        expected=expected_jobs.get(key);body_sha=sha(job['request']);unit=job['unit']
        if expected is not None and expected!=job:raise ValueError('Deferred body differs from saved case replay')
        output=outputs.get(key)
        if output is not None and (output['unit']!=unit or output['request_sha256']!=body_sha):
            raise ValueError('Deferred output changed request identity')
        same_unit=[r for r in records if r['unit']==unit]
        if any(r['request_sha256']!=body_sha for r in same_unit):raise ValueError('Physical unit has a different request')
        reservation=reservations.get(key)
        if reservation is not None and reservation['request_sha256']!=body_sha:
            raise ValueError('Journal unit has a different request')
        same_wire=[r for r in records if r['request_sha256']==body_sha]
        status=('RETAIN_ORIGINAL_NO_BASELINE_REFILL' if unit['method']=='ORIGINAL' else
                'ALREADY_HAS_LOGICAL_OUTPUT_DO_NOT_RESEND' if output is not None else
                'PHYSICAL_ATTEMPT_EXISTS_DO_NOT_RESEND' if same_unit else
                'JOURNAL_ENTRY_EXISTS_WITHOUT_OUTPUT_DO_NOT_RESEND' if reservation is not None else
                'WAIT_FOR_COMPLETED_CASE_EXPORT' if expected is None else
                'SAME_WIRE_FAILED_OR_UNKNOWN_DO_NOT_RESEND' if any(r['status']!='OK' for r in same_wire) else
                'EXACT_SUCCESS_WITNESS_AVAILABLE' if same_wire else 'CONFIRMED_UNISSUED_IN_CURRENT_STAGE')
        results.append({'unit':unit,'request_sha256':body_sha,'sampling_key':key,'classification':status,
                        'manifest_paths':owners[key],'semantic_score_used_for_eligibility':False})
    return {'units':results,'classification_counts':dict(Counter(r['classification'] for r in results)),
            'unique_deferred_units':len(jobs),'confirmed_unissued_not_permission_to_ignore_global_history':True,
            'global_history_inventory_still_required_before_dispatch':True,
            'original_or_failed_requests_not_retried':True,'new_model_calls':0,
            'old_waves_or_scores_modified':False,'goal_complete':False}
