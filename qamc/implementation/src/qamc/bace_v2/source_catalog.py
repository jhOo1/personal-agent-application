"""Program-owned full-unit spans; models select IDs, never write offsets."""
import hashlib
import json


def catalog(units):
    result = {}
    for unit in units:
        text = unit['exact_text']
        if not isinstance(text, str) or not text:
            raise ValueError('Nonempty original text required')
        identity = [unit['source_id'], unit['unit_id'], text, unit.get('memory_version')]
        key = 'S:' + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:24]
        if key in result:
            raise ValueError('Duplicate source identity')
        # Whole existing units retain their original qualifiers and Unicode.
        # Local offsets are explicit; no invented absolute source coordinates.
        result[key] = {'span_id': key, 'source_id': unit['source_id'],
                       'unit_id': unit['unit_id'], 'start': 0, 'end': len(text),
                       'offset_basis': 'provided_unit_exact_text', 'exact_text': text,
                       'source_version': hashlib.sha256(text.encode()).hexdigest(),
                       'parent_context_ids': [], 'source_role': unit.get('carrier'),
                       'recorded_at': unit.get('time'), 'original_metadata': dict(unit)}
    return result


def resolve(table, span_id, version):
    if span_id not in table:
        raise ValueError('Unknown source ID; no fuzzy repair')
    item = table[span_id]
    if item['source_version'] != version:
        raise ValueError('Stale source version')
    return dict(item)
