"""Offline reconciliation of a dead local worker, never a request retry.

An absent owner proves no local stream reader remains, not what the upstream
service did. Pending receipt/journal preimages are archived before moving to
terminal delivery-unknown and installing a no-replay logical result.
"""
from pathlib import Path
import json
import os
import sqlite3
import time

from qamc.common import sha
from qamc.transport_helpers import atomic_json
from qamc.bace.runtime import runner_lock
from proposals.qamc_protocol_alignment.sampling import sampling_key, validate_public_request

ERROR = 'local_worker_absent_without_final_receipt'
ERROR_TYPE = 'LocalWorkerAbsentDeliveryUnknown'


def pid_exists(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError('Explicit positive owner PID required')
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def settle(run_dir, archive_dir, owner_pid):
    run_dir, archive_dir = Path(run_dir), Path(archive_dir)
    if pid_exists(owner_pid):
        raise ValueError('Owner is still live; do not interrupt or settle its requests')
    with runner_lock(run_dir / 'runner.lock'):
        if pid_exists(owner_pid):
            raise ValueError('Owner PID became live; no mutation')
        event_path = archive_dir / 'EVENT.json'
        if event_path.exists():
            event = json.loads(event_path.read_text())
            if event['owner_pid'] != owner_pid or event['run_dir'] != str(run_dir.resolve()):
                raise ValueError('Recovery event belongs to a different owner/run')
        else:
            pending = []
            for path in sorted(run_dir.glob('*/execution/visible/*/record.json')):
                record = json.loads(path.read_text())
                if record['status'] != 'PENDING_DELIVERY_UNKNOWN':
                    continue
                key = sampling_key(record['unit'])
                if key != path.parent.name or path.with_name('response.json').exists():
                    raise ValueError('Pending receipt has response data or inconsistent identity; inspect first')
                request_path = path.with_name('request.json')
                request = json.loads(request_path.read_text())
                validate_public_request(request)
                if sha(request) != record['request_sha256']:
                    raise ValueError('Pending request/receipt hash mismatch')
                block = path.relative_to(run_dir).parts[0]
                db_path = run_dir / block / 'execution/samples.sqlite'
                with sqlite3.connect('file:' + str(db_path) + '?mode=ro', uri=True) as db:
                    row = db.execute('SELECT * FROM samples WHERE unit_key=?', (key,)).fetchone()
                if not row or row[4] != 'STARTED_DELIVERY_UNKNOWN' or row[5] is not None:
                    raise ValueError('Journal has completion/other state; do not discard a saved result')
                if row[2] != record['request_sha256'] or json.loads(row[1]) != record['unit'] or json.loads(row[3]) != request:
                    raise ValueError('Journal and visible receipt disagree')
                relative = path.relative_to(run_dir)
                target = {**record, 'status': 'FAILED_DELIVERY_UNKNOWN', 'error': ERROR,
                          'local_reconciliation': {'owner_pid': owner_pid, 'service_outcome': 'UNKNOWN',
                            'new_model_calls': 0, 'usage_imputed': False,
                            'original_pending_record_sha256': sha(path.read_bytes())}}
                output = {'unit': record['unit'], 'request_sha256': record['request_sha256'],
                          'origin': 'LOCAL_INTERRUPTION_RECONCILIATION', 'status': 'FAILED',
                          'error_type': ERROR_TYPE, 'error': ERROR,
                          'transport_status': 'FAILED_DELIVERY_UNKNOWN', 'service_outcome': 'UNKNOWN',
                          'physical_request_already_registered': True, 'new_physical_request': False}
                output_path = run_dir / block / 'outputs' / (key + '.json')
                if output_path.exists():
                    raise ValueError('A logical result already exists; inspect before changing anything')
                for source in (path, request_path):
                    dest = archive_dir / 'preimages' / source.relative_to(run_dir)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    data = source.read_bytes()
                    if dest.exists() and dest.read_bytes() != data:
                        raise ValueError('Archived preimage differs')
                    dest.write_bytes(data)
                pending.append({'record_path': str(relative), 'block': block, 'unit_key': key,
                    'old_sqlite_row': list(row), 'target_record': target, 'target_output': output})
            if not pending:
                raise ValueError('No orphaned pending deliveries to settle')
            event = {'owner_pid': owner_pid, 'owner_confirmed_absent': True,
                     'run_dir': str(run_dir.resolve()), 'created_unix': time.time(),
                     'entries': pending, 'new_model_calls': 0, 'service_outcomes_unknown': True}
            atomic_json(event_path, event)
        if pid_exists(owner_pid):
            raise ValueError('Owner PID became live; leave archived state intact')
        for block in sorted({e['block'] for e in event['entries']}):
            with sqlite3.connect(run_dir / block / 'execution/samples.sqlite', timeout=10) as db:
                db.execute('BEGIN IMMEDIATE')
                for entry in [e for e in event['entries'] if e['block'] == block]:
                    row = db.execute('SELECT * FROM samples WHERE unit_key=?', (entry['unit_key'],)).fetchone()
                    old = entry['old_sqlite_row']
                    if list(row) == old:
                        db.execute('UPDATE samples SET status=?,error_type=? WHERE unit_key=?',
                                   ('FAILED_DELIVERY_UNKNOWN', ERROR_TYPE, entry['unit_key']))
                    elif list(row) != [*old[:4], 'FAILED_DELIVERY_UNKNOWN', old[5], ERROR_TYPE]:
                        raise ValueError('Journal changed outside this recovery event')
        for entry in event['entries']:
            path = run_dir / entry['record_path']
            before = archive_dir / 'preimages' / entry['record_path']
            value = json.loads(path.read_text())
            if value != entry['target_record'] and path.read_bytes() != before.read_bytes():
                raise ValueError('Visible record changed outside this recovery event')
            atomic_json(path, entry['target_record'])
            output_path = run_dir / entry['block'] / 'outputs' / (entry['unit_key'] + '.json')
            if output_path.exists() and json.loads(output_path.read_text()) != entry['target_output']:
                raise ValueError('Do not replace an existing logical answer')
            atomic_json(output_path, entry['target_output'])
        result = {'settled_orphaned_units': len(event['entries']), 'new_model_calls': 0,
                  'requests_reissued': 0, 'service_success_or_failure': 'UNKNOWN',
                  'usage_imputed': False, 'original_preimages_preserved': True}
        atomic_json(archive_dir / 'SETTLEMENT.json', result)
        return result
