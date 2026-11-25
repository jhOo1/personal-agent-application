"""Pilot scorers; inference code never receives private reference labels."""
import re
from .scoring import Scorer

PREFERENCE_JUDGE = '''You are given:
1) A single preference attribute.
2) One response written for a given context.
Your task is to judge whether the response follows the preference.
If the response follows the preference, label it as "follow". Otherwise, label it as "do_not_follow".
Only output a JSON object: {"label": "follow" | "do_not_follow"}.'''
COMPLETENESS_JUDGE = '''You are an expert evaluator of task-oriented written messages. You are given the task and the generated message. Evaluate how effectively the message achieves the specified task. First provide a brief explanation. Then rate task fulfillment from 1 (does not achieve the task at all) to 5 (achieves the task very effectively). On the final line output exactly Rating: [[X]], with X an integer from 1 to 5.'''


def persona_score(answer, correct):
    raw = answer.strip()
    if '<final_answer>' in raw: raw = raw.split('<final_answer>')[-1].strip()
    if raw.endswith('</final_answer>'): raw = raw[:-len('</final_answer>')].strip()
    def options(text):
        text = text.lower()
        parens = re.findall(r'\(([a-d])\)', text)
        return set(parens or re.findall(r'\b([a-d])\b', text))
    target = correct.lower().strip('() ')
    return {'metric':'official_option_parser_accuracy', 'accuracy':int(options(raw)=={target} or options(answer)=={target}), 'extracted':sorted(options(raw))}


class PilotScorer:
    def __init__(self, gateway): self.gateway, self.memsyco = gateway, Scorer(gateway)
    def score(self, case, reference, answer, key):
        if case['benchmark'] == 'memsyco': return self.memsyco.score(case,reference,answer,key)
        if case['benchmark'] == 'personamem': return persona_score(answer,reference['correct_answer'])
        if case['benchmark'] != 'benchpres': raise ValueError('unknown benchmark')
        attrs, labels = reference['preference_attribute'], reference['preference_label']
        if len(attrs)!=len(labels): raise ValueError('reference label mismatch')
        decisions = []
        for i, (attribute, allowed) in enumerate(zip(attrs, labels)):
            def check(obj):
                if obj.get('label') not in ('follow','do_not_follow'): raise ValueError('invalid judge label')
            result = self.gateway.object(f'{key}/preference_judge/{i}', PREFERENCE_JUDGE,
                {'preference':attribute,'response':answer},check,2048)
            decisions.append({'preference':attribute,'appropriate':allowed,'label':result['label']})
        raw = self.gateway.complete(key+'/completeness_judge',COMPLETENESS_JUDGE,
                                    {'task':case['query'],'response':answer},2048)
        m = re.search(r'Rating:\s*\[\[([1-5])\]\]\s*$',raw)
        if not m: raise ValueError('completeness judge format invalid')
        appropriate = [d for d in decisions if d['appropriate']]
        inappropriate = [d for d in decisions if not d['appropriate']]
        return {'metric':'BenchPreS_Qwen_judge_variant','decisions':decisions,
                'aar_numerator':sum(d['label']=='follow' for d in appropriate),'aar_denominator':len(appropriate),
                'mr_numerator':sum(d['label']=='follow' for d in inappropriate),'mr_denominator':len(inappropriate),
                'task_completeness':int(m.group(1)), 'completeness_judge_raw':raw}
