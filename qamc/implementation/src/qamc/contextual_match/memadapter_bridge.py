"""Pinned author MemAdapter requests, without importing its API client/runner.

The author prompt text and pure builders/validators are read from immutable Git
blobs. No third-party prompt is shortened, and no current task enters Stage 1.
This module builds requests only; durable dispatch and retries belong to the
experiment runner. It is separate from the already frozen P2 generation code.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess


AUTHOR_COMMIT = '6b517dc90d4c7e0ebc4d2305684d45051f792cc9'
MODULE_PATH = 'methods/memadapter/memadapter.py'
PROMPT_FILES = {
    'Stage1': '01_counterfactual_induction_method_aligned.txt',
    'Stage2': '02_context_aware_reflection_method_aligned.txt',
    'Stage3': '03_memory_use_guided_generation.txt',
}
PURE_FUNCTIONS = {
    'normalize_memories', 'build_stage1_input', 'build_stage2_input',
    'build_stage3_input', 'render_prompt', 'parse_json_response',
    '_require_text', 'validate_stage1', 'validate_stage2', 'load_prompt_parts',
}


def git_blob(repo, relative):
    """Read a pinned object even when the author's checkout is sparse or bare."""
    return subprocess.check_output(['git', '-C', str(repo), 'show', AUTHOR_COMMIT+':'+relative])


def public_query(task):
    # Preserve the actual request. Extra public inputs are a disclosed adapter
    # addition, not a learned instruction or evaluation-specific task route.
    if not task.current_context and not task.fixed_facts:
        return task.query
    return task.query+'\n\nAdditional public current context and shared facts:\n'+json.dumps(
        {'current_context':task.current_context, 'fixed_facts':list(task.fixed_facts)}, ensure_ascii=False)


class MemAdapterBridge:
    def __init__(self, repo):
        self.repo=Path(repo)
        module=git_blob(self.repo,MODULE_PATH)
        self.blobs={MODULE_PATH:module}
        self.prompts={}
        for stage,name in PROMPT_FILES.items():
            path='methods/memadapter/prompts/'+name
            self.blobs[path]=git_blob(self.repo,path)
            self.prompts[name]=self.blobs[path].decode('utf-8')
        # Only the pinned pure functions execute, never top-level author code,
        # imports, CLI parsing, environment configuration, or model clients.
        tree=ast.parse(module.decode('utf-8'))
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in PURE_FUNCTIONS]
        if {n.name for n in functions}!=PURE_FUNCTIONS:
            raise ValueError('Pinned MemAdapter pure interface changed')
        future=ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)
        selected=ast.fix_missing_locations(ast.Module(body=[future,*functions],type_ignores=[]))
        self.functions={'json':json,'re':re,'load_prompt':self.prompts.__getitem__}
        exec(compile(selected,AUTHOR_COMMIT+':'+MODULE_PATH,'exec'),self.functions)
        self.parts={stage:self.functions['load_prompt_parts'](name) for stage,name in PROMPT_FILES.items()}

    def manifest(self):
        return {'author_commit':AUTHOR_COMMIT,'repository':'https://github.com/DEEP-JLU/MemAdapter',
            'assets':{p:hashlib.sha256(b).hexdigest() for p,b in sorted(self.blobs.items())},
            'executed_upstream_functions':sorted(PURE_FUNCTIONS),
            'upstream_top_level_code_executed':False,
            'prompt_source':'complete pinned author blobs, no shortened replacement',
            'stages':'query-blind induction; joint context reflection; guided final generation',
            'native_backbone_and_sampling_reproduced':False,
            'native_json_stage_attempts':3,'bridge_automatically_retries':False,
            'adapter_differences':['public c/F appended to current query only when present',
                'controlled backbone qwen3.8-flash and temperature 0',
                'preprocessing cap 8192 and Actor cap 4096',
                'streaming and durable external ledger',
                'Qwen JSON enforced by full prompt/parser, not transport response_format'],
            'full_system_generator_prompt':'author Stage3, not the shared P2 Actor system prompt'}

    @staticmethod
    def memories(task):
        return [{'memory_id':m.memory_id,'memory_text':m.text} for m in task.memories]

    def parse(self,task,stage,raw):
        if stage not in ('Stage1','Stage2'):
            raise ValueError('Only the first two stages return structured author outputs')
        parsed=self.functions['parse_json_response'](raw,stage=stage)
        self.functions['validate_stage1' if stage=='Stage1' else 'validate_stage2'](parsed,self.memories(task))
        return deepcopy(parsed)

    def request(self,task,stage,previous=None,model='qwen3.8-flash'):
        if stage not in PROMPT_FILES:raise ValueError('Unknown MemAdapter stage')
        memories=self.memories(task)
        if stage=='Stage1':
            if previous is not None:raise ValueError('Stage1 cannot receive task-conditioned intermediate output')
            values={'RETRIEVED_MEMORIES':self.functions['build_stage1_input'](memories)}
        else:
            parsed=deepcopy(previous)
            self.functions['validate_stage1' if stage=='Stage2' else 'validate_stage2'](parsed,memories)
            builder=self.functions['build_stage2_input' if stage=='Stage2' else 'build_stage3_input']
            values=builder(current_query=public_query(task),memories=memories,
                **{'boundary_cards' if stage=='Stage2' else 'use_instructions':parsed})
        system,template=self.parts[stage]
        user=self.functions['render_prompt'](template,values)
        # A change to these settings is a new explicitly frozen model block.
        return {'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':user}],
            'temperature':0,'max_tokens':4096 if stage=='Stage3' else 8192,
            'stream':True,'stream_options':{'include_usage':True}}

    def common_actor_control(self,task,instructions,actor_system,model='qwen3.8-flash'):
        """Keep the mechanism, with a disclosed shared-Actor interface control.

        All raw memories remain visible and get their author use instructions.
        This is not physical filtering and is not the author's Stage3 prompt.
        """
        parsed=deepcopy(instructions)
        self.functions['validate_stage2'](parsed,self.memories(task))
        view={'query':task.query,'current_context':task.current_context,'facts':list(task.fixed_facts),
            'source_evidence':[{'memory_id':m.memory_id,'text':m.text} for m in task.memories],
            'memory_use_instructions':parsed['memory_use_instructions']}
        return {'view':view,'request':{'model':model,
            'messages':[{'role':'system','content':actor_system},{'role':'user','content':json.dumps(view,ensure_ascii=False)}],
            'temperature':0,'max_tokens':4096,'stream':True,'stream_options':{'include_usage':True}}}
