"""Six read-side methods with one shared Actor and durable request identities."""
from pathlib import Path
from qamc.common import sha
from qamc.bace.prepare import small_bundle
from qamc.bace_v2.evaluation import DurableJudge
from qamc.bace.runtime import Steps
from qamc.preference_policy.core import validate_scope
from .core import compile_view

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = ROOT/'prompts/qamc_pa_v1'
ARMS = ('R0','G0','S0','V0','V1','V2')


def prompt(name): return (PROMPTS/(name+'.md')).read_text()


def raw_view(task):
    return {'query':task.query,'current_context':task.current_context,'facts':list(task.fixed_facts),
            'source_evidence':[{'memory_id':m.memory_id,'text':m.text} for m in task.memories]}


class Engine:
    def __init__(self, gateway, run_root):
        self.g = DurableJudge(gateway, Steps(Path(run_root)/'generation_steps.sqlite'))

    def select(self, task, arm):
        if arm not in ARMS: raise ValueError('Unknown arm')
        public = task.payload(); key = 'pa/'+sha([task.uid, public, arm])
        if arm == 'R0': return raw_view(task), None
        if arm == 'S0':
            summary = self.g.complete(key+'/summary', prompt('summary'), public, 8192)
            if not isinstance(summary,str) or not summary.strip(): raise ValueError('Empty summary')
            return {'query':task.query,'current_context':task.current_context,
                    'facts':list(task.fixed_facts),'query_aware_summary':summary}, None
        if arm == 'G0': return self.gate(task,key), None
        selected = self.g.object(key+'/select', prompt('selector_'+arm.lower()), public,
                                 lambda x: compile_view(task,x,arm),8192)
        return compile_view(task,selected,arm), selected

    def gate(self, task, key):
        # Retain legacy scope+gate algorithms/prompts; replace only Actor and
        # hold fact context fixed across arms. Name this adapted, not old B1.
        sources = [{'id':m.memory_id,'content':m.text,'role':'user'} for m in task.memories]
        sources += [{'id':f'FACT{i}','content':s,'role':'user'} for i,s in enumerate(task.fixed_facts)]
        bundle = small_bundle(task.query, sources); payload = bundle['payload']
        payload['current_context'] = [task.current_context] if task.current_context else []
        base = ROOT/'prompts/preference_policy'
        common = (base/'common.md').read_text()
        scope = self.g.object(key+'/scope', common+'\n'+(base/'scope.md').read_text(), payload,
                              lambda x: validate_scope(x,payload),4096)
        inp = {**payload,'scopes':scope['scopes'],'shared_task_unit_ids':scope['task_unit_ids'],
               'allow_policies':[],'deny_policies':[],'policy_version_hash':sha([])}
        ids = {u['unit_id'] for u in payload['units']}
        def check(x):
            if set(x) != {'selected_unit_ids','material_gaps'}: raise ValueError('Gate schema')
            for field in x:
                if not isinstance(x[field],list) or not all(isinstance(v,str) for v in x[field]): raise ValueError('Gate list')
            if not set(x['selected_unit_ids']) <= ids: raise ValueError('Unknown gate unit')
        chosen = self.g.object(key+'/gate',common+'\n'+(base/'gate.md').read_text(),inp,check,8192)
        selected = set(chosen['selected_unit_ids']) | set(scope['task_unit_ids'])
        source_ids = {u['source_id'] for u in payload['units'] if u['unit_id'] in selected}
        view = raw_view(task)
        view['source_evidence'] = [v for v in view['source_evidence'] if v['memory_id'] in source_ids]
        return view

    def answer(self, task, arm, view):
        # Arm only changes evidence, never the Actor system or output limit.
        key = 'pa/actor/'+sha([task.uid,arm,view,prompt('actor')])
        text = self.g.complete(key,prompt('actor'),view,4096)
        if not isinstance(text,str) or not text.strip(): raise ValueError('Empty Actor answer')
        return {'answer':text,'actor_request_hash':sha([prompt('actor'),view,4096]),'view':view}

    def run(self, task, arm):
        view, selection = self.select(task,arm)
        return {**self.answer(task,arm,view),'selection':selection,'arm':arm}

    def no_level(self, task, saved_selection):
        # No second selection. This is the controlled influence-only ablation.
        view = compile_view(task,saved_selection,'V2',show_influence=False)
        return self.answer(task,'V2_NO_LEVEL',view)
