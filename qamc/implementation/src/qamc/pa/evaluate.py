"""Evaluation-only model calls, separate from the public generation engine."""
from pathlib import Path
from qamc.common import sha
from qamc.bace.runtime import Steps
from qamc.bace_v2.evaluation import DurableJudge
from qamc.pilot_scoring import PilotScorer
from .rpeval_scoring import load_rubrics, judge_prompt, parse_score
from . import prefeval_scoring as pref

ROOT=Path(__file__).resolve().parents[3]


class Evaluator:
    def __init__(self,gateway,run_root):
        self.g=DurableJudge(gateway,Steps(Path(run_root)/'evaluation_steps.sqlite'))
        self.bench=PilotScorer(self.g)
        self.rubrics=load_rubrics(ROOT/'literature/qamc_pa_v1/RPEval/prompts/prompts_715.py')

    def score(self,benchmark,uid,query,reference,answer):
        key='pa/eval/'+sha([benchmark,uid,query,reference,answer])
        if benchmark=='benchpres':
            return self.bench.score({'benchmark':'benchpres','query':query},reference,answer,key)
        if benchmark=='rpeval':
            multiple=isinstance(reference['persona'],list)
            count=len(reference['persona']) if multiple else 1
            system='Evaluate the completed answer using the supplied benchmark rubric. Return JSON.'
            payload=judge_prompt(self.rubrics,reference,answer,multiple)
            output=self.g.object(key,system,payload,lambda obj:parse_score(obj,count,multiple),2048)
            return {**parse_score(output,count,multiple),'raw_judge':output,'judge_model_variant':'qwen3.8-flash'}
        if benchmark=='prefeval':
            upstream=ROOT/'vendor/PrefEval';checks={}
            # The hallucination check depends on the saved acknowledgment result.
            for metric in pref.FILES:
                message=pref.build_prompt(upstream,metric,reference,answer,checks)
                raw=self.g.complete(key+'/'+metric,pref.SYSTEM,message,2048)
                checks[metric]=pref.parse_check(upstream,metric,raw)
            return {**pref.aggregate(checks),'checks':checks}
        raise ValueError('Unknown benchmark; no surrogate score')
