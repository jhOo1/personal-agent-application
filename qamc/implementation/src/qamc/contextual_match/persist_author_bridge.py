"""Pinned PersistBench defensive prompts and original renderer, without API code.

This is a controlled-model development adaptation, not the author's provider,
native repeat count, optimized-prompt training procedure or Kimi evaluation.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from qamc.common import parse_object
from .development import text_request

COMMIT='d2ded18be6d15ebb14008d081a44bd03c20670e4'
ASSETS={'module':'src/benchmark/prompts.py','GEPA':'prompts/defensive/GEPA_optimized.txt',
    'RUBRIC':'prompts/defensive/rubric_informed.txt','FILTER':'prompts/llm_retrieval.txt'}
METHODS=('PB_FULL','PB_GEPA','PB_RUBRIC','PB_NO_MEMORY','PB_FILTER_NATIVE','PB_FILTER_COMMON')


class PersistAuthorBridge:
    def __init__(self,repo):
        self.repo=Path(repo)
        self.blobs={key:subprocess.check_output(['git','-C',str(self.repo),'show',COMMIT+':'+path])
            for key,path in ASSETS.items()}
        tree=ast.parse(self.blobs['module'].decode())
        self.template=None
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GENERATOR_SYSTEM_PROMPT' for t in node.targets):
                self.template=ast.literal_eval(node.value)
        if not isinstance(self.template,str):raise ValueError('Pinned author generator template missing')
        names={'formatted_memories','build_generation_prompt'}
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        if {n.name for n in functions}!=names:raise ValueError('Pinned author renderer missing')
        module=ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[]))
        env={'GENERATOR_SYSTEM_PROMPT':self.template}
        exec(compile(module,COMMIT+':'+ASSETS['module'],'exec'),env)
        self.render=env['build_generation_prompt']

    def manifest(self):
        return {'author_repository':'https://github.com/ivaxi0s/PersistBench','author_commit':COMMIT,
            'assets':{ASSETS[k]:hashlib.sha256(v).hexdigest() for k,v in self.blobs.items()},
            'complete_prompts_preserved':True,'upstream_top_level_or_client_executed':False,
            'only_upstream_functions_executed':['formatted_memories','build_generation_prompt'],
            'GEPA_optimizer_rerun':False,'uses_released_optimized_prompt':True,
            'LLM_filter_runner':'reimplementation using complete released prompt and strict original-text subset',
            'semantic_threshold':'NOT_RUN: no executable threshold/retrieval implementation found in pinned source tree',
            'license_status':'No LICENSE-named asset found in inspected pinned tree; no license claim',
            'native_protocol_parity_proven':False,'development_model':'qwen3.8-flash',
            'development_temperature':0,'development_actor_cap':4096,
            'development_repeats':1,'development_judge':'gpt-4.1 strict BU >=3',
            'native_repeats_and_Kimi_provider_reproduction':False}

    @staticmethod
    def require_public(task):
        if task.current_context or task.fixed_facts:
            raise ValueError('Author Persist adapter expects its unmodified q/M-only public input')
        return [m.text for m in task.memories]

    def filter_request(self,task):
        values=self.require_public(task)
        return text_request(self.blobs['FILTER'].decode(),
            json.dumps({'query':task.query,'memories':values},ensure_ascii=False),cap=8192)

    def parse_filter(self,task,answer):
        values=self.require_public(task);obj=parse_object(answer);selected=obj.get('useful_memories')
        if (not isinstance(selected,list) or not all(isinstance(s,str) for s in selected)
                or len(set(selected))!=len(selected) or not set(selected)<=set(values)):
            raise ValueError('Author filter must select unique original memory strings')
        # Do not export the requested step_by_step_reasoning as a new method
        # field. Only original-text membership controls the next Actor input.
        return [m.memory_id for m in task.memories if m.text in selected]

    def actor(self,task,method,actor_system,selected=None):
        values=self.require_public(task)
        if method not in METHODS:raise ValueError('Unknown Persist author control')
        filtering=method in ('PB_FILTER_NATIVE','PB_FILTER_COMMON')
        if filtering:
            if (not isinstance(selected,list) or len(set(selected))!=len(selected)
                    or not set(selected)<={m.memory_id for m in task.memories}):
                raise ValueError('Filtered Actor needs validated source IDs')
            evidence=[{'memory_id':m.memory_id,'text':m.text} for m in task.memories if m.memory_id in selected]
            values=[v['text'] for v in evidence]
        elif method=='PB_NO_MEMORY':values=[]
        if method=='PB_FILTER_COMMON':
            view={'query':task.query,'current_context':task.current_context,'facts':list(task.fixed_facts),
                'source_evidence':evidence}
            return {'view':view,'request':text_request(actor_system,view,cap=4096),'table_track':'SHARED_ACTOR'}
        template=self.blobs[method.removeprefix('PB_')].decode() if method in ('PB_GEPA','PB_RUBRIC') else self.template
        system=self.render(values,'qwen3.8-flash',template)
        view={'query':task.query,'original_memory_texts':deepcopy(values),'author_system_prompt':system}
        return {'view':view,'request':text_request(system,task.query,cap=4096),'table_track':'AUTHOR_GENERATOR_ADAPTED_MODEL'}
