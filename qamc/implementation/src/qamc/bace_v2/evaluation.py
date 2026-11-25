"""Evaluation-only boundary, including complete official attribute denominators."""
from pathlib import Path
from qamc.bace.runtime import Steps
from qamc.bace.prefeval_adapter import score as prefeval_score
from qamc.pilot_scoring import PilotScorer
from qamc.common import sha
from qamc.transport_helpers import atomic_json


class DurableJudge:
    def __init__(self, gateway, steps):
        self.gateway = gateway; self.steps = steps

    def complete(self, key, system, payload, maximum):
        request = {'model': self.gateway.model, 'system': system, 'payload': payload,
                   'max_tokens': maximum, 'temperature': 0}
        return self.steps.run(key + '/' + sha(request), request,
            lambda: self.gateway.complete(key + '/' + sha(request), system, payload, maximum))

    def object(self, key, system, payload, check, maximum):
        request = {'model': self.gateway.model, 'system': system, 'payload': payload,
                   'max_tokens': maximum, 'temperature': 0}
        return self.steps.run(key + '/' + sha(request), request,
            lambda: self.gateway.object(key + '/' + sha(request), system, payload, check, maximum))


class Evaluator:
    def __init__(self, gateway, root):
        self.root = Path(root)
        self.steps = Steps(self.root / 'evaluation_steps.sqlite')
        self.scorer = PilotScorer(DurableJudge(gateway, self.steps))

    def score(self, case, reference, answer_result):
        # Receive full native reference only here, never a selected-use subset.
        identity = sha([case, reference, answer_result['answer'], 'native_variant_v1'])
        directory = self.root / 'scores' / identity[:24]
        directory.mkdir(parents=True, exist_ok=True)
        record = {'uid': answer_result['uid'], 'arm': answer_result['arm'],
                  'answer_request_hash': answer_result['actor_request_hash'],
                  'answer_status': 'ANSWER_COMPLETE', 'score_input_hash': identity}
        try:
            if case['benchmark'] == 'prefeval':
                score = prefeval_score(answer_result['answer'], reference)
            elif case['benchmark'] == 'benchpres':
                score = self.scorer.score(case, reference, answer_result['answer'], 'bace_v2/eval/' + identity)
                assert score['aar_denominator'] + score['mr_denominator'] == len(reference['preference_attribute'])
            else: raise ValueError('Unsupported primary benchmark')
            record.update(score_status='OK', score=score)
        except Exception as exc:
            record.update(score_status='FAILED', score=None, error_type=type(exc).__name__, error=str(exc))
        atomic_json(directory / (sha([record['uid'],record['arm']])[:24] + '.json'), record)
        return record
