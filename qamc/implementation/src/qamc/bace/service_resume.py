"""Read-only service recovery preparation; never clears STOP or dispatches."""
import argparse
import json
import sqlite3
from .audit import OUT, digest
from .prepare import RUN
from .eval import verify
from .runtime import runner_lock
from qamc.transport_helpers import atomic_json


def resume_inventory(plan, requests, step_keys):
    # An in-flight or unresolved delivery must reach a recorded terminal state.
    if any(r['status'] == 'pending_delivery_unknown' for r in requests):
        raise ValueError('In-flight requests must finish before recovery planning')
    if len(requests) >= plan['request_cap']:
        raise ValueError('Parent request cap exhausted')
    allowed = []
    for case in plan['cases']:
        if case['phase'] != 'score-pilot':
            continue
        prefix = case['uid'] + '/'
        # Even a failed or STARTED logical step is not a fresh case.
        if any(r['key'].startswith(prefix) for r in requests):
            raise ValueError('Development case already has a physical request')
        if any(k.startswith(prefix) for k in step_keys):
            raise ValueError('Development case already has a retained logical step')
        allowed.append(case['uid'])
    errors = [r['request_id'] for r in requests
              if r['status'] in {'protocol_error', 'transport_error_delivery_unknown'}
              and r.get('usage') is None and r.get('upstream_status') != 429]
    return {'allowed_uids': allowed, 'parent_request_count': len(requests),
            'request_cap': plan['request_cap'],
            'remaining_requests': plan['request_cap'] - len(requests),
            'retained_unknown_error_ids': errors,
            'new_epoch_failure_count_starts_after_request_id': max(
                (r['request_id'] for r in requests), default=0),
            'failed_or_completed_regression_retry_allowed': False,
            'service_recovery_confirmed': False, 'dispatch_allowed': False,
            'new_model_calls': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true', required=True)
    parser.parse_args()
    with runner_lock(RUN / 'runner.lock'):
        plan = verify()
        stop = RUN / 'api/STOP'
        if not stop.exists():
            raise ValueError('No retained service stop to reconcile')
        with sqlite3.connect(f'file:{RUN}/api/ledger.sqlite?mode=ro', uri=True) as db:
            requests = [json.loads(r[0]) for r in db.execute('SELECT data FROM requests')]
        with sqlite3.connect(f'file:{RUN}/anchored_span_v3/steps.sqlite?mode=ro', uri=True) as db:
            keys = [r[0] for r in db.execute('SELECT key FROM steps')]
        record = resume_inventory(plan, requests, keys)
        record.update(stop_sha256=digest(stop),
                      frozen_plan_sha256=digest(OUT / 'SCORE_PILOT_PLAN.json'),
                      instructions='Requires explicit service recovery evidence and a frozen recovery runner; this command does not clear STOP.')
        atomic_json(OUT / 'SERVICE_RESUME_PREPARATION.json', record)
        print(json.dumps(record))


if __name__ == '__main__':
    main()
