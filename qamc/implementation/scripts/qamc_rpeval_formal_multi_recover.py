"""Settle an interrupted formal RPEval wave without repeating any request."""
import argparse
from collections import Counter
from pathlib import Path
import sqlite3

import qamc_rpeval_formal_multi_run as run
from qamc.contextual_match.interrupted_delivery import pid_exists, settle
from qamc.transport_helpers import atomic_json


def recover(owner):
    plan = run.prepare()
    run.check(plan, True)
    archive = run.OUT / f'worker_interruption_{owner}'
    acceptance = archive / 'ACCEPTANCE.json'
    if acceptance.exists():
        return run.read(acceptance)
    state = run.read(run.OUT / 'RUN_STATE.json')
    if state.get('phase') != 'RUNNING' or state.get('pid') != owner or pid_exists(owner):
        raise ValueError('Recovery requires the recorded owner to have exited')
    block = state['model_block']
    manifest = run.read(run.OUT / block / 'stage_manifests' / f"component_{state['stage']}.json")
    if manifest['protocol'] != plan['protocols'][block]:
        raise ValueError('Interrupted stage protocol differs from the frozen plan')
    jobs = {run.sampling_key(j['unit']): j for j in manifest['units']}
    allowed = set(plan['allowed_unit_keys'])
    receipts = list(run.RUN.glob('*/execution/visible/*/record.json'))
    event = archive / 'EVENT.json'
    pending = ({run.RUN / e['record_path'] for e in run.read(event)['entries']} if event.exists()
               else {p for p in receipts if run.read(p)['status'] == 'PENDING_DELIVERY_UNKNOWN'})
    for path in pending:
        record = run.read(path)
        key = run.sampling_key(record['unit'])
        request = run.read(path.with_name('request.json'))
        if (key not in allowed or run.block(record['unit']['stage']) != block
                or jobs.get(key) != {'unit': record['unit'], 'request': request}
                or run.sha(request) != record['request_sha256']):
            raise ValueError('Interrupted request differs from the frozen stage allocation')
    # This incident has a receipt for every claimed unit and a saved output for
    # every settled attempt. Stop if a different crash boundary needs analysis.
    for protocol in plan['protocols']:
        folder = run.RUN / protocol
        journal = folder / 'execution/samples.sqlite'
        if not journal.exists():
            continue
        with sqlite3.connect(journal.as_uri() + '?mode=ro', uri=True) as db:
            journal_rows = db.execute('SELECT unit_key FROM samples').fetchall()
        for (key,) in journal_rows:
            record = folder / 'execution/visible' / key / 'record.json'
            if not record.exists() or (record not in pending and not (folder/'outputs'/f'{key}.json').exists()):
                raise ValueError('A journal claim needs separate reconciliation')

    waves = sorted((run.OUT / 'waves').glob('*.json'))
    outputs = list(run.RUN.glob('*/outputs/*.json'))
    if event.exists():
        targets = {run.RUN / e['block'] / 'outputs' / (e['unit_key']+'.json')
                   for e in run.read(event)['entries']}
        outputs = [p for p in outputs if p not in targets]
    protected = {str(p.relative_to(run.ROOT)): run.pin(p)
                 for p in [*waves, *outputs, *(p for p in receipts if p not in pending)]}
    run.frozen(archive / 'PROTECTED_FILES.json', protected)
    run.frozen(archive / 'PRIOR_RUN_STATE.json', state)
    run.frozen(archive / 'PRIOR_PACING.json', run.read(run.RUN / 'PACING.json'))
    result = settle(run.RUN, archive, owner)
    if any(run.pin(run.ROOT / name) != digest for name, digest in protected.items()):
        raise ValueError('A completed output changed during recovery')
    now = [run.read(p) for p in run.RUN.glob('*/execution/visible/*/record.json')]
    if len(now) != len(receipts) or any(r['status'] == 'PENDING_DELIVERY_UNKNOWN' for r in now):
        raise ValueError('Physical request count changed or a receipt remains pending')
    evidence = {**result, 'physical_requests': len(now), 'completed_waves': len(waves),
                'receipt_statuses': dict(Counter(r['status'] for r in now)),
                'protected_completed_files': len(protected)}
    run.frozen(acceptance, evidence)
    atomic_json(run.OUT / 'RUN_STATE.json', {
        'phase': 'INTERRUPTION_RECONCILED_READY_TO_RESUME', 'pid': None,
        'previous_worker_pid': owner, 'completed_waves': len(waves),
        'settled_delivery_unknown': len(pending), 'goal_complete': False,
    })
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('owner_pid', type=int)
    print(recover(parser.parse_args().owner_pid))
