"""Secondary spelling/unused-field compatibility; no new selection policy.

Keep strict-v1 records. An explicitly nonconditional source marked MATCHED
already has positive task support; the guard never tests that field for this
role. Normalize only this dead-field form, with the original task quote checked.
Contradictory/unknown states, missing actions, source mismatches and actual
conditional decisions are never repaired.
"""
from copy import deepcopy
import json

from qamc.common import parse_object, sha
from . import conditional_transfer

POLICY = 'nonconditional_positive_match_compatibility_v2'


def actor(task, raw, prompts, guarded):
    obj = deepcopy(parse_object(raw));changes = []
    if not isinstance(obj, dict):raise ValueError('Expected transfer object')
    checks = obj.get('transfer_checks')
    if isinstance(checks, dict):
        for mid, row in checks.items():
            if not isinstance(row, dict):continue
            if row.get('role') in {'END_OR_TASTE', 'CONTINUING_CONSTRAINT', 'OTHER_OR_MIXED'} and row.get('match') == 'MATCHED':
                anchor = row.get('task_anchor')
                if not isinstance(anchor, str) or not anchor.strip() or not any(anchor in text for text in [task.query, task.current_context]):
                    raise ValueError('Do not normalize an invalid positive task quote')
                changes.append({'memory_id': mid, 'role': row['role'], 'old_match': 'MATCHED',
                                'old_task_anchor': anchor, 'new_match': 'NOT_REQUIRED'})
                row.update(match='NOT_REQUIRED', task_anchor=None)
    built = conditional_transfer.actor(task, json.dumps(obj, ensure_ascii=False), prompts, guarded)
    return {**built, 'transfer_codec_audit': {'policy': POLICY, 'original_prediction_sha256': sha(raw),
        'normalized_prediction': obj, 'changes': changes, 'new_semantic_selection': False}}
