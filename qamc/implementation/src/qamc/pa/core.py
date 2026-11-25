"""Public-input boundary and deterministic original-source compilation.

This module has no model, Store, gold-label or filesystem access.
"""
from dataclasses import dataclass, asdict
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Memory:
    memory_id: str
    text: str
    # Only pre-existing trusted source boundaries can enable partial selection.
    ranges: tuple = ()

    def spans(self):
        ranges = self.ranges or ((0, len(self.text)),)
        previous = 0
        result = {}
        for index, (start, end) in enumerate(ranges):
            if not (previous <= start < end <= len(self.text)):
                raise ValueError('Invalid or overlapping source boundaries')
            result[f'{self.memory_id}:S{index}'] = self.text[start:end]
            previous = end
        # Gaps containing semantic text would silently discard qualifiers.
        covered = ''.join(self.text[a:b] for a, b in ranges)
        if ''.join(covered.split()) != ''.join(self.text.split()):
            raise ValueError('Source boundaries omit non-whitespace content')
        return result


@dataclass(frozen=True)
class PublicTask:
    uid: str
    query: str
    memories: tuple
    current_context: str = ''
    fixed_facts: tuple = ()

    def payload(self):
        if len({m.memory_id for m in self.memories}) != len(self.memories):
            raise ValueError('Duplicate memory identity')
        return {'query': self.query, 'current_context': self.current_context,
                'fixed_facts': list(self.fixed_facts),
                'memories': [{'memory_id': m.memory_id, 'text': m.text,
                              'spans': m.spans()} for m in self.memories]}


def rpeval_public(row, uid, implicit=False):
    # Explicit persona and gold explanations must never leak into implicit inputs.
    key = 'implicit_persona' if implicit else 'persona'
    raw = row[key]
    values = raw if isinstance(raw, list) else [raw]
    if not values or not all(isinstance(v, str) and v.strip() for v in values):
        raise ValueError('Unsupported upstream memory shape; no silent conversion')
    query = row['question']
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Missing query')
    return PublicTask(uid, query, tuple(Memory(f'M{i}', text) for i, text in enumerate(values)))


def compile_view(task, selection, variant, show_influence=True):
    """Validate sparse decisions; never fall back to raw history on failure."""
    if variant not in {'V0', 'V1', 'V2'}:
        raise ValueError('Unknown variant')
    if set(selection) != {'preference_actions', 'unresolved_ids'}:
        raise ValueError('Unexpected selector fields, including fact selection')
    memories = {m.memory_id: m for m in task.memories}
    task.payload()
    unresolved = selection['unresolved_ids']
    if not isinstance(unresolved, list) or len(unresolved) != len(set(unresolved)) or not set(unresolved) <= memories.keys():
        raise ValueError('Invalid unresolved IDs')
    rows = selection['preference_actions']
    if not isinstance(rows, list):
        raise ValueError('Actions must be a list')
    seen = set(); evidence = []
    for row in rows:
        fields = {'memory_id', 'decision', 'keep_span_ids'}
        if variant == 'V2': fields.add('influence')
        if set(row) != fields: raise ValueError('Unexpected action fields')
        mid = row['memory_id']
        if mid not in memories or mid in seen: raise ValueError('Unknown or duplicate memory')
        seen.add(mid)
        memory = memories[mid]; spans = memory.spans()
        decision = row['decision']; kept = row['keep_span_ids']
        allowed = {'APPLY', 'DROP'} if variant == 'V0' else {'APPLY', 'DROP', 'PARTIAL'}
        if decision not in allowed: raise ValueError('Invalid decision')
        if not isinstance(kept, list) or len(set(kept)) != len(kept) or not set(kept) <= spans.keys():
            raise ValueError('Unknown or duplicate span')
        if decision == 'DROP' and kept: raise ValueError('DROP leaks source')
        if decision == 'APPLY' and set(kept) != spans.keys(): raise ValueError('APPLY must preserve whole source')
        if decision == 'PARTIAL' and not 0 < len(kept) < len(spans): raise ValueError('PARTIAL requires proper subset')
        if mid in unresolved and decision != 'DROP': raise ValueError('Uncertainty is not permission')
        if variant == 'V2':
            level = row['influence']
            if (decision == 'DROP' and level != 'NONE') or (decision != 'DROP' and level not in {'SUPPORT', 'DOMINATE'}):
                raise ValueError('Inconsistent influence')
        if decision == 'DROP': continue
        # Source order, not model-specified ordering; APPLY preserves exact original.
        text = memory.text if decision == 'APPLY' else '\n'.join(v for k, v in spans.items() if k in kept)
        item = {'memory_id': mid, 'text': text}
        if variant == 'V2' and show_influence: item['influence'] = row['influence']
        evidence.append(item)
    if seen != memories.keys(): raise ValueError('Incomplete memory coverage')
    evidence.sort(key=lambda item: list(memories).index(item['memory_id']))
    return {'query': task.query, 'current_context': task.current_context,
            'facts': list(task.fixed_facts), 'source_evidence': evidence}
