"""Materialize provenance-carrying facets from an existing memory snapshot."""
from __future__ import annotations
from datetime import datetime, timezone


def _timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def materialize_profile(store, snapshot_id, as_of_time=None):
    cutoff = _timestamp(as_of_time) if as_of_time else None
    if as_of_time and cutoff is None:
        raise ValueError('invalid profile history cutoff')
    facets = []
    for record in store.records():
        recorded = _timestamp(record.recorded_at)
        # An unparseable recorded timestamp cannot certify historical availability.
        if cutoff and record.recorded_at and (recorded is None or recorded > cutoff):
            continue
        if record.fields:
            fields = [(k, v, record.field_supports.get(k) or record.source_refs)
                      for k, v in record.fields.items() if k not in record.stale_fields]
        elif record.status_reason == 'source_changed_requires_regeneration':
            fields = []
        else:
            fields = [(record.attribute or 'claim', record.content, record.source_refs)]
        for name, value, refs in fields:
            resolved = []
            for ref in refs:
                parent = store.get(ref)
                resolved.extend(parent.source_refs if parent else [ref])
            resolved = list(dict.fromkeys(resolved))
            sources = [store.source(ref) for ref in resolved]
            if not value or not resolved or any(source is None for source in sources):
                continue
            # A summary can incorporate a later or undated source even when the
            # summary itself has no timestamp. Never silently retain only some
            # sources while keeping a claim derived from all of them.
            if cutoff:
                dates = [_timestamp(source.get('recorded_at')) for source in sources]
                if any(date is None or date > cutoff for date in dates):
                    continue
            facets.append({'facet_id': record.memory_id + ':' + name,
                'memory_id': record.memory_id, 'attribute': name, 'value': value,
                'subject': record.subject, 'scope': record.scope or {},
                'semantic_type': record.semantic_type, 'source_kind': record.source_kind,
                'recorded_at': record.recorded_at, 'valid_from': record.valid_from,
                'valid_to': record.valid_to, 'pool': record.pool,
                'status_reason': record.status_reason, 'source_refs': resolved,
                'snapshot_id': snapshot_id, 'as_of_time': as_of_time})
    return facets
