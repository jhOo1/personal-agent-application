"""One authorized service epoch for the frozen, never-dispatched D_cal cases."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from .audit import ROOT, OUT, digest
from .prepare import RUN
from .span_revision import prepare, NEW
from .service_resume import resume_inventory
from .runtime import runner_lock, BaceGateway, Steps
from .span_adapter import SpanGateway
from .engine import ScoreEngine
from qamc.common import sha
from qamc.transport_helpers import atomic_json


def epoch_unknown_failures(requests, after):
    return [r for r in requests if r['request_id'] > after
            and r['status'] in {'protocol_error', 'transport_error_delivery_unknown'}
            and r.get('usage') is None and r.get('upstream_status') != 429]


def main():
    with runner_lock(RUN / 'runner.lock'):
        plan, _ = prepare()
        freeze = json.loads((OUT / 'SERVICE_RECOVERY_EPOCH1.json').read_text())
        if freeze['authorization']['answer'] != '已确认恢复，可接续未派发任务':
            raise ValueError('Missing explicit recovery evidence')
        for name, expected in freeze['frozen_files'].items():
            if digest(ROOT / name) != expected:
                raise ValueError('Recovery runner drift')
        if not json.loads((OUT / 'SCORE_SMOKE_V2_GATE.json').read_text())['passed']:
            raise ValueError('Recovered smoke gate required')
        stop = RUN / 'api/STOP'
        if not stop.exists() or digest(stop) != freeze['stop_sha256']:
            raise ValueError('Original service stop must match; no implicit restart')
        with sqlite3.connect(f'file:{RUN}/api/ledger.sqlite?mode=ro', uri=True) as db:
            requests = [json.loads(r[0]) for r in db.execute('SELECT data FROM requests')]
        with sqlite3.connect(f'file:{NEW}/steps.sqlite?mode=ro', uri=True) as db:
            keys = [r[0] for r in db.execute('SELECT key FROM steps')]
        live = resume_inventory(plan, requests, keys)
        for key in ('allowed_uids', 'parent_request_count', 'request_cap',
                    'new_epoch_failure_count_starts_after_request_id'):
            if live[key] != freeze[key]:
                raise ValueError('Recovery preflight state changed: ' + key)
        archive = NEW / 'SERVICE_STOP_EPOCH0.txt'
        if archive.exists():
            raise ValueError('Recovery epoch already started')
        base = BaceGateway(RUN / 'api', request_cap=plan['request_cap'],
                           concurrency=8, spacing_seconds=6.1)
        if base.disabled:
            raise ValueError('Separate model-disable reconciliation required')
        # Archive only the exact stop covered by this user-confirmed epoch.
        stop.rename(archive)
        engine = ScoreEngine(SpanGateway(base), Steps(NEW / 'steps.sqlite'))
        cases = [c for c in plan['cases'] if c['uid'] in freeze['allowed_uids']]

        def one(case):
            directory = NEW / 'cases' / sha(case['uid'])[:24]
            path = directory / 'result.json'
            if path.exists():
                return json.loads(path.read_text())
            if base.disabled or stop.exists():
                return {'uid': case['uid'], 'status': 'NOT_DISPATCHED'}
            directory.mkdir(parents=True, exist_ok=True)
            result = {'uid': case['uid'], 'phase': 'score-pilot',
                      'input_hash': case['bundle_sha256'], 'service_epoch': 1}
            try:
                scores = engine.score(case['uid'], json.loads((ROOT / case['bundle']).read_text()),
                                      case['scopes'], directory)
                result.update(status='OK', uses=len(scores['inventory']),
                              overflow=len(scores['unassessed_overflow']))
            except Exception as exc:
                result.update(status='FAILED', error_type=type(exc).__name__,
                              error=str(exc), semantic_score=None)
                with base.lock:
                    rows = [json.loads(r[0]) for r in base.db.execute('SELECT data FROM requests')]
                    if len(epoch_unknown_failures(rows, freeze['new_epoch_failure_count_starts_after_request_id'])) >= 2:
                        stop.write_text('Two unknown transport failures in recovery epoch1; no blind retry.\n')
                        base.disabled = True
            atomic_json(path, result)
            print(json.dumps(result), flush=True)
            return result

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = [f.result() for f in as_completed([pool.submit(one, c) for c in cases])]
        base.export()
        atomic_json(OUT / 'SCORE_PILOT_V3_RUN.json', {
            'phase': 'score-pilot', 'namespace': 'anchored_span_v3', 'service_epoch': 1,
            'cases': results, 'passed': all(r['status'] == 'OK' for r in results),
            'claims_semantic_gain': False})


if __name__ == '__main__':
    main()
