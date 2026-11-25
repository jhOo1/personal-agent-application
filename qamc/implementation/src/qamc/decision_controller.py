"""Shared candidate preparation and four read-side comparisons."""
from .actor import Actor
from .candidate_ids import resolve_candidate_aliases
from .common import ROOT
from .decision_binding import UnifiedBinder, build_decision_view
from .evidence_compiler import source_pack
from .profile_view import materialize_profile, _timestamp


def validate_gate(result, candidates, sources):
    if not isinstance(result.get('selected'), list):
        raise ValueError('missing selected list')
    lookup = {c['id']: c for c in candidates}
    raw = {s['id']: s['content'] for s in sources}
    for item in result['selected']:
        doc = lookup.get(item.get('candidate_id'))
        if not doc or not item.get('spans'):
            raise ValueError('unknown candidate or empty spans')
        for span in item['spans']:
            sid, quote = span.get('source_id'), span.get('quote')
            if sid not in doc['source_ids'] or not quote or quote not in raw.get(sid, ''):
                raise ValueError('invalid candidate provenance')
    return result


def verify_store_prefix(case, store):
    """A store cannot contribute sources outside the exact inference history."""
    turns = case['history']
    allowed = {turn['id']: turn for turn in turns}
    if len(allowed) != len(turns):
        raise ValueError('history source IDs must be unique')
    cutoff = _timestamp(case.get('query_time')) if case.get('query_time') else None
    if case.get('query_time') and cutoff is None:
        raise ValueError('invalid query time')
    for source in store.sources():
        original = allowed.get(source['id'])
        if original is None or source != original:
            raise ValueError('store contains source outside frozen inference history')
        recorded = _timestamp(source.get('recorded_at'))
        if cutoff and source.get('recorded_at') and recorded is None:
            raise ValueError('source recorded time is invalid')
        if cutoff and recorded and recorded > cutoff:
            raise ValueError('store contains a source after query time')



def selection_inputs(shared):
    """Represent each profile facet once while retaining its visible candidate ID."""
    profile=[{**c['metadata'],'candidate_id':c['id']} for c in shared['candidates'] if c['kind']=='profile']
    candidates=[c for c in shared['candidates'] if c['kind']!='profile']
    return profile,candidates



class DecisionComparison:
    def __init__(self, gateway, retriever):
        if retriever.top_k != 24:
            raise ValueError('pilot requires top_k=24')
        self.gateway, self.retriever = gateway, retriever
        self.binder = UnifiedBinder(gateway)
        self.actor = Actor(gateway)
        self.actor.prompt = (ROOT / 'prompts/actor_decision_binding.md').read_text()
        self.gate_prompt = (ROOT / 'prompts/semantic_gate.md').read_text()

    def prepare(self, case, store, snapshot_id):
        verify_store_prefix(case, store)
        # Query alone drives shared retrieval; no benchmark references or answers.
        task = {'goal': case['query'], 'time_mode': 'unspecified'}
        candidates = self.retriever.search(task, store)
        profile = materialize_profile(store, snapshot_id, case.get('query_time'))
        facets = [{'id':'facet:' + f['facet_id'], 'kind':'profile', 'text':f['value'],
                   'source_ids':f['source_refs'], 'metadata':f} for f in profile]
        shared = candidates + facets
        sources = source_pack(store, shared, 24000)
        # Omit facets whose supporting sources did not fit the shared source budget.
        source_ids = {s['id'] for s in sources}
        shared = [c for c in shared if set(c.get('source_ids', [])) & source_ids]
        profile = [c['metadata'] for c in shared if c['kind'] == 'profile']
        return {'candidates': shared, 'profile': profile, 'sources': sources,
                'retrieved_ids':[c['id'] for c in candidates], 'top_k':24}

    def answer(self, case, shared, method, key, checkpoint=None):
        query, context = case['query'], case.get('current_context', [])
        if method == 'B0':
            view = {'history':case['history']}
            detail = {}
        elif method == 'B1':
            view = {'candidates':shared['candidates'], 'source_evidence':shared['sources']}
            detail = {}
        elif method == 'B2':
            model_profile,model_candidates=selection_inputs(shared)
            payload = {'query':query, 'current_context':context, 'profile':model_profile,
                       'candidates':model_candidates, 'source_evidence':shared['sources']}
            def validate_and_normalize(obj):
                corrections=resolve_candidate_aliases(obj,'selected',shared['candidates'])
                validate_gate(obj,shared['candidates'],shared['sources'])
                if corrections:obj.setdefault('id_resolution',[]).extend(corrections)
            selection = self.gateway.object(key + '/gate', self.gate_prompt, payload,
                validate_and_normalize, 8192)
            view = {'selected_evidence':selection['selected']}
            detail = {'gate':selection}
        elif method == 'B3':
            model_profile,model_candidates=selection_inputs(shared)
            binding = self.binder.bind(query, context, model_profile, model_candidates, shared['sources'], key + '/binder',
                                       validation_candidates=shared['candidates'])
            view = build_decision_view(binding)
            detail = {'binding':binding}
        else:
            raise ValueError('unknown method')
        # Persist intermediate selection before the Actor request so a failed
        # or delivery-unknown Actor does not erase the path to the failure.
        if checkpoint is not None:
            checkpoint({'actor_view':view, 'stage_reached':'actor_ready', **detail})
        answer = self.actor.generate(query, context, view, key + '/actor', case.get('query_time'))
        return {'answer':answer, 'actor_view':view, **detail}
