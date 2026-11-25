"""Isolated author controls with shared pacing; prepare/report make no calls."""
import argparse
from copy import deepcopy
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]
import qamc_contextual_match_persist_authors as source
import qamc_contextual_match_v2_review_window as review
import qamc_contextual_match_v2_external_continue_v2 as external
from qamc.common import sha, canonical, token_estimate
from qamc.contextual_match.cache_inventory import inventory
from qamc.contextual_match.cache import service_filtered
from qamc.contextual_match.external_continuation_v2 import ReadOnlyContinuationRuntime
from qamc.contextual_match.phase_runtime import PhaseDispatcher, model_block
from qamc.contextual_match.review_pacing_v2 import SharedGate, PacedControl
from qamc.bace.runtime import runner_lock
from qamc.transport_helpers import atomic_json, read_reference
from proposals.qamc_protocol_alignment.sampling import sampling_key

OUT = ROOT/'reports/qamc_contextual_match_v2_20261112/persist_author_controls_v2'
RUN = ROOT/'runs/qamc_contextual_match_v2_20261112/persist_author_controls_v2'
read, frozen = source.read, source.frozen
PersistAuthorBridge = source.PersistAuthorBridge
parent, ext, collect_wave = source.parent, source.ext, source.collect_wave


def check(plan, service=True):
    saved = read(OUT/'PLAN.json')
    if sha({k: v for k, v in plan.items() if k != 'protocol'}) != sha(saved):
        raise ValueError('Author control plan drift')
    if service and read_reference()[1] != plan['service_reference_sha256']:
        raise ValueError('Service identity changed')
    if len(plan['allowed_unit_keys']) != 780 or len(set(plan['allowed_unit_keys'])) != 780:
        raise ValueError('Author allocation changed')
    for path, expected in plan['files'].items():
        if parent.audit.file_sha(ROOT/path) != expected:
            raise ValueError('Pinned author control dependency changed: '+path)
    if PersistAuthorBridge(parent.persist.UP).manifest() != plan['author_manifest']:
        raise ValueError('Author Git assets changed')
    if any(source.RUN.glob('*/execution/visible/*/record.json')) or any(source.RUN.glob('*/outputs/*.json')):
        raise ValueError('Old author namespace gained outcomes; explicit migration now required')


def prepare():
    if (OUT/'PLAN.json').exists():
        plan = read(OUT/'PLAN.json'); check(plan, False); return plan
    old = read(source.OUT/'PLAN.json'); source.check(old, False)
    plan = deepcopy(old)
    for block, protocol in plan['protocols'].items():
        protocol.update(namespace='qamc_contextual_match_v2_20261112/persist_author_controls_v2/'+block,
                        spacing_seconds=3.2, stream_cooldown_seconds=301)
    units = []
    for case in plan['cases']:
        units.append(source.unit(plan, case['uid'], 'PB_FILTER_SHARED', 'Selector'))
        for method in plan['methods']:
            units.extend(source.unit(plan, case['uid'], method, stage) for stage in ('Actor', 'PersistJudge'))
    plan.update(allowed_unit_keys=sorted(sampling_key(u) for u in units),
                source_plan_sha256=sha(old), previous_review_and_external_terminal_required=True,
                new_global_budget_created=False, new_samples=0)
    pins = [Path(__file__), source.OUT/'PLAN.json', review.OUT/'PLAN.json', external.OUT/'PLAN.json']
    for module in list(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file:
            path = Path(file).resolve()
            if path.is_relative_to(ROOT) and path.suffix == '.py': pins.append(path)
    plan['files'] = {**old['files'], **parent.audit.pins(pins)}
    frozen(OUT/'PLAN.json', plan); check(plan, False)
    frozen(OUT/'COST_FORECAST.json', {'selector_slots': 60, 'actor_slots': 360, 'judge_slots': 360,
        'maximum_new_physical_calls': 780, 'exact_cache_can_reduce_calls': True,
        'failed_or_unknown_attempts_never_resent': True, 'new_global_budget_created': False,
        'new_samples': 0, 'native_repeat_protocol': False, 'prepare_model_calls': 0})
    print({'prepared': True, 'maximum_new_calls': 780, 'model_calls': 0})
    return plan


class Dispatcher(PhaseDispatcher):
    def __init__(self, plan):
        super().__init__(ROOT, OUT, RUN, plan, check, 'qamc_contextual_match_v2_20261112/persist_author_controls_v2')
        self.gate = SharedGate(RUN/'timing/SHARED_PACING.json', spacing=3.2, cooldown=301)
        until = 0.
        for prior in (review.RUN, external.RUN):
            for path in prior.glob('*/execution/visible/*/record.json'):
                record = read(path)
                if record['status'] not in ('OK', 'PENDING_DELIVERY_UNKNOWN'):
                    until = max(until, record['started_unix']+record.get('elapsed_seconds', 0)+301)
        with self.gate.lock:
            self.gate.until = max(self.gate.until, self.gate.mono()+max(0., until-time.time()))
            self.gate._save()

    def sampler(self, *args, **kwargs):
        sampler = super().sampler(*args, **kwargs)
        sampler.control = PacedControl(sampler.control, self.gate)
        return sampler

    def grade_batches(self, runtime, name, jobs, index):
        pending = [j for j in jobs if runtime.resolve(j['unit'], j['request'], index) is None]
        for offset in range(0, len(pending), 8):
            batch = pending[offset:offset+8]; self.gate.wait_ready()
            runtime.stage({**self.plan, 'protocol': self.plan['protocols']['gpt41']}, 'author_controls',
                          name+'_'+sha([j['unit'] for j in batch])[:20], batch, index)
            if self.gate.hard: raise RuntimeError('Authentication/quota hard stop')

    def dispatch(self, name, jobs):
        if not jobs: return
        check(self.plan)
        for job in jobs: self.validate_job(job)
        for block, runtime in self.runtimes.items():
            eligible = []
            for job in jobs:
                if model_block(job['unit']['stage']) != block: continue
                body = canonical(job['request']['messages'])
                if token_estimate(body) > 32768 or len(body.encode()) > 2_000_000:
                    frozen(runtime.run/'outputs'/(sampling_key(job['unit'])+'.json'),
                           {'unit': job['unit'], 'request_sha256': sha(job['request']),
                            'status': 'CAPACITY_BLOCKED', 'origin': 'OFFLINE_CAPACITY_GUARD',
                            'new_physical_request': False})
                else: eligible.append(job)
            if not eligible: continue
            wanted = {sha(j['request']) for j in eligible}
            index = service_filtered(ROOT, inventory(ROOT, wanted), wanted, self.plan['service_reference_sha256'])
            if index['schema_skips']: raise ValueError('Unknown historical journal schema')
            frozen(OUT/block/'cache_snapshots'/(name+'_'+sha(index)+'.json'), index)
            self.gate.wait_ready()
            atomic_json(OUT/'RUN_STATE.json', {'phase': 'RUNNING', 'pid': os.getpid(), 'stage': name,
                'model_block': block, 'eligible_units': len(eligible), 'updated_unix': time.time(), 'goal_complete': False})
            if block == 'gpt41': self.grade_batches(runtime, name, eligible, index)
            else: runtime.stage({**self.plan, 'protocol': self.plan['protocols'][block]}, 'author_controls', name, eligible, index)
            if self.gate.hard: raise RuntimeError('Authentication/quota hard stop')


def require_predecessors():
    external.require_review_terminal()
    if read(external.OUT/'RUN_STATE.json').get('phase') != 'EXTERNAL_CONTINUATION_TERMINAL':
        raise RuntimeError('External continuation not terminal')
    if any(read(p)['status'] == 'PENDING_DELIVERY_UNKNOWN' for p in external.RUN.glob('*/execution/visible/*/record.json')):
        raise RuntimeError('External requests still in flight')
    if len(list((external.OUT/'waves').glob('*.json'))) != 13:
        raise RuntimeError('External continuation lacks all waves')


def main(action):
    plan = read(OUT/'PLAN.json') if action == 'report' else prepare()
    check(plan, action == 'run')
    if action == 'prepare': return
    bridge = PersistAuthorBridge(parent.persist.UP)
    if action == 'report':
        runtimes = {b: ReadOnlyContinuationRuntime(ROOT, RUN/b, {}) for b in ('qwen', 'gpt41')}
        verified = []
        for path in sorted((OUT/'waves').glob('*.json')):
            saved = read(path)
            if collect_wave(plan, saved['wave'], runtimes, lambda *_: None, bridge) != saved:
                raise ValueError('Saved author wave replay changed')
            verified.append(saved['wave'])
        atomic_json(OUT/'REPORT_REPLAY.json', {'verified_waves': verified, 'new_model_calls': 0, 'goal_complete': False})
        print({'verified_waves': len(verified), 'new_model_calls': 0}); return
    require_predecessors()
    with ExitStack() as stack:
        for prior in (parent.RUN, ext.RUN, source.RUN, review.RUN, external.RUN, RUN):
            stack.enter_context(runner_lock(prior/'runner.lock'))
        require_predecessors(); dispatcher = Dispatcher(plan)
        for wave in range(len(plan['waves'])):
            path = OUT/'waves'/f'{wave:02d}.json'
            if not path.exists(): frozen(path, collect_wave(plan, wave, dispatcher.runtimes, dispatcher.dispatch, bridge))
        atomic_json(OUT/'RUN_STATE.json', {'phase': 'AUTHOR_CONTROLS_TERMINAL', 'pid': None,
            'completed_waves': list(range(13)), 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'report'))
    main(parser.parse_args().action)
