"""Shared source organization, complete review batches and final Actor output."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from qamc.common import sha, ROOT
from qamc.bace.runtime import Steps
from qamc.transport_helpers import atomic_json
from .organizer import compile_organization
from .reviewers import validate_reviews, qualitative_routes
from .use_inventory import batches
from .execution import AnswerExecutor

PROMPTS = ROOT / 'prompts/bace_v2'


def prompt(name): return (PROMPTS / (name + '.md')).read_text()


REVIEW_SCHEMA = '''Return {"assessments":[{"use_id":"provided ID","finding":"role-specific state",
"refs":["source or query ID"],"reason":"brief evidence-based reason","raw_score":null,
"uncertainty":"","issue_type":null}]}. Allow issue_type must be null.
Deny ISSUE_FOUND needs one of WRONG_SUBJECT_OR_RECIPIENT, CURRENT_REQUIREMENT_CONFLICT,
CONTEXTUAL_MISFIT, BELIEF_AS_WORLD_FACT, STATE_OR_TIME_ERROR, UNNECESSARY_DISCLOSURE,
OVEREXTENDED_INFLUENCE. Other Deny states use null. Include every use exactly once.'''


class ReviewEngine:
    def __init__(self, gateway, root, actor_prompt):
        self.gateway = gateway; self.root = Path(root)
        self.steps = Steps(self.root / 'review_steps.sqlite')
        self.actor = AnswerExecutor(gateway, self.root, actor_prompt)

    def object(self, uid, stage, system, payload, validator):
        request = {'system': system, 'payload': payload, 'model': self.gateway.model,
                   'temperature': 0, 'max_tokens': 8192}
        key = 'bace_v2/' + uid + '/' + stage + '/' + sha(request)
        return self.steps.run(key, request, lambda: self.gateway.object(
            key, system, payload, validator, 8192))

    def organize(self, uid, payload, sources, queries, schema):
        public = {'query': payload['query'], 'current_context': payload.get('current_context', []),
                  'query_time': payload.get('query_time'),
                  'sources': sources, 'query_sources': queries, 'output_schema': schema}
        output = self.object(uid, 'organization', prompt('organizer'), public,
                             lambda o: compile_organization(o, sources, queries))
        organized = compile_organization(output, sources, queries)
        directory = self.root / 'organization' / sha(uid)[:24]
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / 'organization.json', organized)
        return organized

    def review(self, uid, arm, payload, sources, queries, organized):
        if arm not in {'B2', 'B3', 'M0'}: raise ValueError('Unknown review arm')
        allowed_refs = set(sources) | set(queries)
        all_allow = []; all_deny = []
        for number, batch in enumerate(batches(organized['uses'])):
            public = {'query': payload['query'], 'current_context': payload.get('current_context', []),
                      'query_time': payload.get('query_time'), 'task_frame': organized['task_frame'],
                      'sources': sources, 'query_sources': queries, 'uses': batch}
            def check_role(obj, role):
                if not isinstance(obj, dict) or set(obj) != {'assessments'}:
                    raise ValueError('Role output schema mismatch')
                validate_reviews(obj['assessments'], batch, role, allowed_refs)
            def role(which):
                return self.object(uid, f'{arm}/batch{number}/{which}', prompt(which)+'\n'+REVIEW_SCHEMA,
                                   public, lambda o: check_role(o, which))
            def check_joint(obj):
                if not isinstance(obj, dict) or set(obj) != {'allow', 'deny'}:
                    raise ValueError('Joint output schema mismatch')
                for which in ('allow', 'deny'): check_role(obj[which], which)
            if arm == 'M0':
                with ThreadPoolExecutor(max_workers=2) as pool:
                    a = pool.submit(role, 'allow'); d = pool.submit(role, 'deny')
                    output = {'allow': a.result(), 'deny': d.result()}
            else:
                system = (prompt('allow')+'\n'+prompt('deny')+'\n'+REVIEW_SCHEMA+
                          '\nAct as a balanced joint reviewer. Return {"allow":role_object,"deny":role_object}. '
                          'Assess both legitimate value and contextual harm; neither side is predetermined.')
                output = self.object(uid, f'{arm}/batch{number}/joint', system, public, check_joint)
                if arm == 'B3':
                    output = self.object(uid, f'{arm}/batch{number}/recheck', system+
                        '\nIndependently check the initial review against original sources. Correct omissions and '
                        'unsupported judgments; keep valid assessments. Do not generate an answer.',
                        {**public, 'initial_review': output}, check_joint)
            all_allow.extend(output['allow']['assessments']); all_deny.extend(output['deny']['assessments'])
        routes = qualitative_routes(organized['uses'], all_allow, all_deny)
        disputed = [r['use_id'] for r in routes if r['action'] == 'REVIEW']
        # One task-level resolution, not one unbounded conversation per use.
        if disputed:
            def check_resolution(obj):
                if not isinstance(obj, dict) or set(obj) != {'decisions'}: raise ValueError('Resolution schema')
                rows = obj['decisions']
                if len(rows) != len(disputed) or {r['use_id'] for r in rows} != set(disputed):
                    raise ValueError('Incomplete dispute resolution')
                for row in rows:
                    if set(row) != {'use_id', 'action', 'refs', 'reason'}: raise ValueError('Decision fields')
                    if row['action'] not in {'KEEP', 'OMIT', 'UNRESOLVED'}: raise ValueError('Repair not enabled')
                    if not isinstance(row['refs'], list) or not set(row['refs']) <= allowed_refs:
                        raise ValueError('Invalid resolution references')
                    if not isinstance(row['reason'], str): raise ValueError('Decision reason required')
            without_scores = lambda rows: [{k:v for k,v in row.items() if k != 'raw_score'} for row in rows]
            output = self.object(uid, arm+'/resolve', prompt('resolver')+
                '\nThis arm disables REPAIR. Resolve all disputed IDs once. Return {"decisions":'
                '[{"use_id":"ID","action":"KEEP|OMIT|UNRESOLVED","refs":[],"reason":"brief"}]}.',
                {'query': payload['query'], 'task_frame': organized['task_frame'],
                 'sources': sources, 'query_sources': queries, 'uses': organized['uses'],
                 'disputed_ids': disputed, 'initial_routes': routes,
                 'allow': without_scores(all_allow), 'deny': without_scores(all_deny)}, check_resolution)
            resolved = {r['use_id']: r for r in output['decisions']}
            routes = [resolved.get(r['use_id'], r) for r in routes]
        trace = {'allow': all_allow, 'deny': all_deny, 'decisions': routes,
                 'batch_count': len(batches(organized['uses'])), 'resolver_calls': int(bool(disputed))}
        directory = self.root / 'reviews' / sha([uid, arm])[:24]
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / 'trace.json', trace)
        return self.actor.reviewed(uid, arm, payload, sources, organized, routes)
