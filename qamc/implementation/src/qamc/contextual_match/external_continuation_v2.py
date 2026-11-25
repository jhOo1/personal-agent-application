"""Finite external allocation and deterministic imported-result recovery."""
from copy import deepcopy
from qamc.common import sha
from .external_import_recovery_v2 import ImportedAuthorRetryRuntime, authorize_with_evidence, imported_completed_record
from .baseline_recovery import completed_record
from .actor_window_audit_v2 import SavedRuntime
from proposals.qamc_pa_transfer.cache_acceleration import prefilter_exact
from proposals.qamc_protocol_alignment.sampling import sampling_key
from proposals.qamc_sentence_units.runtime import frozen


def all_units(plan):
    """Reconstruct and verify every original slot, including unused author retries."""
    units = {}
    def add(uid, method, stage, replicate=0):
        block = 'gpt41' if stage in ('RPEvalJudge', 'PersistJudge') else 'qwen'
        u = {'protocol_sha256': sha(plan['protocols'][block]), 'root_id': uid,
             'method': method, 'stage': stage, 'replicate': replicate}
        key = sampling_key(u)
        if key in units and units[key] != u:
            raise ValueError('Allocation identity collision')
        units[key] = u
    for j in plan['initial_requests']:
        u = j['unit']; add(u['root_id'], u['method'], u['stage'], u['replicate'])
        if u['stage'] == 'MemInduction':
            for attempt in (1, 2): add(u['root_id'], u['method'], 'MemInductionRecovery', attempt)
    for c in plan['cases']:
        add(c['uid'], 'MEMADAPTER_SHARED', 'MemReflection')
        for attempt in (1, 2): add(c['uid'], 'MEMADAPTER_SHARED', 'MemReflectionRecovery', attempt)
        methods = plan['methods'] if c['benchmark'] == 'rpeval' else [m for m in plan['methods'] if m != 'INCREMENTAL_NATIVE_FORMAT']
        judges = (['RPEvalJudge'] if c['benchmark'] == 'rpeval' else
                  [*(f'BenchAttr{i}' for i in range(5)), 'BenchComplete'] if c['benchmark'] == 'benchpres' else ['PersistJudge'])
        for method in methods:
            for stage in ('Actor', *judges): add(c['uid'], method, stage)
    if set(units) != set(plan['allowed_unit_keys']) or len(units) != plan['logical_guard']:
        raise ValueError('Reconstructed external allocation differs from original frozen slots')
    return units


def map_units(value, protocol_map):
    if isinstance(value, list): return [map_units(v, protocol_map) for v in value]
    if isinstance(value, dict):
        if set(value) == {'protocol_sha256', 'root_id', 'method', 'stage', 'replicate'}:
            return {**value, 'protocol_sha256': protocol_map[value['protocol_sha256']]}
        return {k: map_units(v, protocol_map) for k, v in value.items()}
    return value


class ExternalContinuationRuntime(ImportedAuthorRetryRuntime):
    """Use fixed source outcomes first; new aliases follow physical cache order.

    Rehashing protocol namespaces must not change which stochastic cached answer
    wins merely by changing lexical unit filenames. Ordinary cross-unit reuse
    therefore uses the established exact physical-path cache selector, not the
    new namespace's output filename order. No score is consulted.
    """
    def resolve(self, unit, request, index):
        key = sampling_key(unit); saved = self.output(unit)
        if saved:
            if saved['request_sha256'] != sha(request): raise ValueError('Saved continuation wire changed')
            if key in self.import_bindings and sha(saved) != self.import_bindings[key]['imported_output_sha256']:
                raise ValueError('Imported fixed outcome changed')
            return saved
        if unit['stage'] in ('MemInductionRecovery', 'MemReflectionRecovery'):
            return super().resolve(unit, request, index)
        cached = prefilter_exact(self.root, index, request)
        if cached['state'] == 'NOT_FOUND_IN_AUDITED_NAMESPACES': return None
        value = {'unit': unit, 'request_sha256': sha(request), 'new_physical_request': False,
                 'origin': 'EXACT_HISTORICAL_IMPORT' if cached['state'] == 'EXACT_SUCCESS' else 'PRIOR_ATTEMPT_RETAINED',
                 'status': 'OK' if cached['state'] == 'EXACT_SUCCESS' else 'PRIOR_ATTEMPT_RETAINED',
                 'cache_lineage': {k: v for k, v in cached.items() if k != 'response'}}
        if cached['state'] == 'EXACT_SUCCESS': value['response'] = deepcopy(cached['response'])
        frozen(self.run/'outputs'/(key+'.json'), value)
        return value


class ReadOnlyContinuationRuntime(SavedRuntime):
    def __init__(self, root, run, bindings):
        super().__init__(run); self.root, self.bindings = root, bindings
    def authorize(self, previous, job, validator):
        if previous is None: return None
        key = sampling_key(previous['unit'])
        evidence = (imported_completed_record(self.root, previous, self.bindings[key]) if key in self.bindings
                    else completed_record(self, previous))
        return authorize_with_evidence(previous, job, validator, evidence)
