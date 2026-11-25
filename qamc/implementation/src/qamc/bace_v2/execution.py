"""Durable final-answer execution shared by the new review arms and Strong."""
from pathlib import Path
from qamc.common import sha
from qamc.bace.runtime import Steps
from qamc.transport_helpers import atomic_json
from .actor_view import compile_view, raw_view


class AnswerExecutor:
    def __init__(self, gateway, root, actor_prompt):
        self.gateway = gateway
        self.root = Path(root)
        self.steps = Steps(self.root / 'answer_steps.sqlite')
        self.actor_prompt = actor_prompt

    def answer(self, uid, arm, view, audit=None):
        # Content-addressed cache binds model, prompt, sources, view and limits.
        request = {'model': self.gateway.model, 'temperature': 0, 'max_tokens': 4096,
                   'system': self.actor_prompt, 'payload': view}
        identity = sha(request)
        key = 'bace_v2/' + uid + '/' + arm + '/actor/' + identity
        directory = self.root / 'answers' / sha([uid, arm, identity])[:24]
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / 'actor_input.json', request)
        if audit is not None: atomic_json(directory / 'view_audit.json', audit)
        response = self.steps.run(key, request, lambda: self.gateway.complete(
            key, self.actor_prompt, view, 4096))
        result = {'uid': uid, 'arm': arm, 'answer': response,
                  'actor_request_hash': identity, 'status': 'ANSWER_COMPLETE',
                  'native_score_status': 'NOT_YET_SCORED'}
        atomic_json(directory / 'answer.json', result)
        return result

    def strong(self, uid, payload, sources):
        return self.answer(uid, 'B0', raw_view(payload, sources))

    def reviewed(self, uid, arm, payload, sources, organized, decisions):
        view, audit = compile_view(payload, sources, organized, decisions)
        return self.answer(uid, arm, view, audit)
