"""Preserve author retry evidence when terminal outputs move to a new namespace.

This is experiment recovery infrastructure, not a memory-selection mechanism.
No API calls, score access or changes to source receipts occur here.
"""
from copy import deepcopy
from pathlib import Path

from qamc.common import sha
from .review_imports_v2 import receipt, read
from .actor_window_audit_v2 import SavedRuntime
from .baseline_recovery import completed_record, AuthorRetryRuntime
from proposals.qamc_protocol_alignment.sampling import sampling_key
from proposals.qamc_sentence_units.runtime import frozen


def within(root, value):
    path = (Path(root)/value).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Imported author receipt escapes repository')
    return path


def import_terminal(root, source_path, new_unit):
    source_path = within(root, source_path)
    original = read(source_path)
    if any(original['unit'][k] != new_unit[k] for k in ('root_id', 'method', 'stage', 'replicate')):
        raise ValueError('Namespace import changed source, method or author attempt')
    if original['status'] not in ('OK', 'FAILED', 'PRIOR_ATTEMPT_RETAINED'):
        raise ValueError('Only terminal recorded outputs may be imported')
    value, refs = receipt(root, source_path, new_unit)
    # A known failed author attempt must remain FAILED, rather than silently
    # losing its bounded recovery eligibility after a namespace migration.
    if original['status'] == 'FAILED':
        value['status'] = 'FAILED'
        for name in ('error', 'error_type'):
            if name in original:
                value[name] = original[name]
    binding = {'source_path': str(source_path.relative_to(Path(root).resolve())),
               'source_output_sha256': sha(original), 'source_unit': original['unit'],
               'imported_unit': new_unit, 'imported_output_sha256': sha(value),
               'original_status': original['status'], 'request_sha256': original['request_sha256'],
               'references': {str(p.relative_to(Path(root).resolve())): sha(read(p)) for p in refs},
               'new_physical_request': False, 'scores_consulted': False}
    return value, binding


def imported_completed_record(root, previous, binding):
    if (previous['unit'] != binding['imported_unit'] or sha(previous) != binding['imported_output_sha256']
            or previous['request_sha256'] != binding['request_sha256']):
        raise ValueError('Imported author output or binding changed')
    source = within(root, binding['source_path'])
    original = read(source)
    if (sha(original) != binding['source_output_sha256'] or original['unit'] != binding['source_unit']
            or original['status'] != binding['original_status']
            or any(original['unit'][k] != previous['unit'][k] for k in ('root_id', 'method', 'stage', 'replicate'))):
        raise ValueError('Original author output changed')
    for name, expected in binding['references'].items():
        if sha(read(within(root, name))) != expected:
            raise ValueError('Imported public witness changed')
    # Apply the original DONE/stop-or-length rule to the original namespace.
    # A missing receipt, unknown delivery or cached response without an author
    # completion witness remains ineligible; do not infer that it finished.
    return completed_record(SavedRuntime(source.parent.parent), original)


def authorize_with_evidence(previous, next_job, validator, evidence):
    unit = next_job['unit']
    if unit['stage'] not in ('MemInductionRecovery', 'MemReflectionRecovery') or unit['replicate'] not in (1, 2):
        raise ValueError('Only the frozen three-attempt author JSON policy may recover')
    if previous:
        prior = previous['unit']
        expected_stage = unit['stage'].removesuffix('Recovery') if unit['replicate'] == 1 else unit['stage']
        if (any(prior[k] != unit[k] for k in ('protocol_sha256', 'root_id', 'method'))
                or prior['stage'] != expected_stage or prior['replicate'] != unit['replicate']-1):
            raise ValueError('Author retry changed identity or skipped an attempt')
    if evidence is None or previous is None:
        return None
    path, record = evidence
    if (record.get('received_done') is not True
            or record.get('status') not in ('OK', 'KNOWN_LENGTH_FAILURE')
            or record.get('finish_reason') != ('stop' if record.get('status') == 'OK' else 'length')
            or record.get('request_sha256') != previous['request_sha256']):
        return None
    original = read(path.with_name('request.json'))
    without_cap = lambda b: {k: v for k, v in b.items() if k != 'max_tokens'}
    if without_cap(original) != without_cap(next_job['request']) or next_job['request']['max_tokens'] != 16384:
        raise ValueError('Author retry changed messages/model or recovery cap')
    if record['status'] == 'OK':
        try:
            validator(previous['response']['answer'])
        except (ValueError, TypeError, KeyError) as exc:
            reason = {'type': 'AUTHOR_JSON_CONTRACT', 'error_type': type(exc).__name__}
        else:
            return None
    else:
        reason = {'type': 'PROVEN_DONE_LENGTH', 'error_type': 'finish_length'}
    return {'unit': unit, 'request_sha256': sha(next_job['request']),
            'previous_unit': previous['unit'], 'previous_request_sha256': previous['request_sha256'],
            'physical_record': str(path), 'physical_record_sha256': sha(record), 'reason': reason,
            'semantic_scores_consulted': False, 'automatic_unknown_delivery_retry': False}


class ImportedAuthorRetryRuntime(AuthorRetryRuntime):
    """Retain the old retry policy, with explicit immutable import provenance."""
    def __init__(self, *args, import_bindings=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.import_bindings = deepcopy(import_bindings or {})

    def authorize(self, previous, next_job, validator):
        key = sampling_key(previous['unit']) if previous else None
        if key not in self.import_bindings:
            return super().authorize(previous, next_job, validator)
        binding = self.import_bindings[key]
        evidence = imported_completed_record(self.root, previous, binding)
        result = authorize_with_evidence(previous, next_job, validator, evidence)
        if result is None:
            return None
        result['import_binding_sha256'] = sha(binding)
        next_key = sampling_key(next_job['unit'])
        frozen(self.out/'retry_authorizations'/(next_key+'.json'), result)
        self.retry_validators[next_key] = validator
        return result
