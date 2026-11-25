"""Validate a model's bindings and build a source-bound actor view."""
from __future__ import annotations

from .common import ROOT
from .candidate_ids import resolve_candidate_aliases

ROLES = {'FACT_SUPPORT', 'CONSTRAINT', 'SOFT_PREFERENCE', 'STYLE', 'USER_VIEW', 'HISTORY'}
SELECTIONS = {'USE', 'CONTEXT_ONLY', 'EXCLUDE'}
VALIDITY = {'CURRENT', 'HISTORICAL', 'DISPUTED', 'UNKNOWN'}
APPLICABILITY = {'APPLICABLE', 'PARTIAL', 'INAPPLICABLE', 'UNKNOWN'}
NECESSITY = {'REQUIRED', 'USEFUL', 'NOT_NEEDED', 'UNKNOWN'}
SUPPORT = {'DIRECT', 'SUPPORTED_INFERENCE', 'PARTIAL', 'NONE'}


def validate_binding(result, query, candidates, sources):
    decisions = result.get('decisions')
    if not isinstance(decisions, list) or not decisions:
        raise ValueError('missing decisions')
    ids = set()
    for decision in decisions:
        did = decision.get('id')
        anchors = decision.get('query_anchors')
        if not did or did in ids or not anchors or not all(a and a in query for a in anchors):
            raise ValueError('decision must have unique id and verbatim query anchor')
        ids.add(did)
    candidate_ids = {c['id'] for c in candidates}
    source_map = {s['id']: s for s in sources}
    for item in result.get('bindings', []):
        if item.get('decision_id') not in ids or item.get('candidate_id') not in candidate_ids:
            raise ValueError('unknown decision or candidate')
        if item.get('role') not in ROLES or item.get('selection') not in SELECTIONS:
            raise ValueError('invalid binding role or selection')
        if (item.get('validity') not in VALIDITY or item.get('applicability') not in APPLICABILITY
                or item.get('necessity') not in NECESSITY or item.get('support_mode') not in SUPPORT):
            raise ValueError('missing or invalid validity, applicability, necessity or support')
        if item.get('applicability') == 'INAPPLICABLE' and item['selection'] == 'USE':
            raise ValueError('inapplicable evidence cannot be selected for use')
        if not item.get('aspect') or not item.get('effect'):
            raise ValueError('missing aspect or effect')
        spans = item.get('spans') or []
        if item['selection'] != 'EXCLUDE' and not spans:
            raise ValueError('included binding requires source evidence')
        for span in spans:
            source = source_map.get(span.get('source_id'))
            text = span.get('quote')
            if not source or not text or text not in source.get('content', ''):
                raise ValueError('unverifiable source quote')
            candidate = next(c for c in candidates if c['id'] == item['candidate_id'])
            if span['source_id'] not in candidate.get('source_ids', []):
                raise ValueError('source is not linked to candidate')
    if not isinstance(result.get('bindings'), list):
        raise ValueError('missing bindings')
    return result


def build_decision_view(result):
    view = []
    for decision in result['decisions']:
        entries = []
        for binding in result['bindings']:
            if binding['decision_id'] != decision['id'] or binding['selection'] == 'EXCLUDE':
                continue
            entries.append({k: binding.get(k) for k in ('candidate_id', 'aspect', 'role', 'effect',
                            'selection', 'validity', 'applicability', 'necessity', 'support_mode', 'boundary', 'spans')})
        # Answer formatting is governed by the identical actor prompt for all arms.
        # Binder-authored answer contracts and answer forms remain diagnostic only.
        actor_decision = {k: decision.get(k) for k in ('id', 'goal', 'subject', 'query_anchors')}
        view.append({'decision': actor_decision, 'evidence': entries})
    return {'decisions': view, 'critical_gaps': result.get('critical_gaps', [])}


class UnifiedBinder:
    def __init__(self, gateway):
        self.gateway = gateway
        self.prompt = (ROOT / 'prompts' / 'unified_binder.md').read_text()

    def bind(self, query, current_context, profile, candidates, sources, key, validation_candidates=None):
        # Facets are included in candidates, with the same provenance checks as retrieval.
        visible_candidates = validation_candidates if validation_candidates is not None else candidates
        def validate_and_normalize(obj):
            corrections = resolve_candidate_aliases(obj, 'bindings', visible_candidates)
            validate_binding(obj, query, visible_candidates, sources)
            if corrections:
                obj.setdefault('id_resolution', []).extend(corrections)
        return self.gateway.object(key, self.prompt, {'query': query,
            'current_context': current_context, 'profile': profile, 'candidates': candidates,
            'source_evidence': sources}, validate_and_normalize, 8192)
