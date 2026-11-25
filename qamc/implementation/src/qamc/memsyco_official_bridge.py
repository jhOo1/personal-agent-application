"""Execute upstream rubric builders and parsers, with a transport-only bridge.

No upstream answer generator, memory policy or gold is imported into methods.py.
Dependency-free AST loading preserves upstream function bodies and judge prompts.
"""
from __future__ import annotations
import ast, json, re, types, contextvars
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]
UPSTREAM=ROOT/'vendor'/'MemSyco-Bench'/'evaluation'
_reply=contextvars.ContextVar('official_judge_reply')

def _load(path, roots, external=None):
    source=path.read_text(); tree=ast.parse(source)
    definitions={n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    constants={}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            try: value=ast.literal_eval(n.value)
            except Exception: value=None
            for target in n.targets:
                if isinstance(target,ast.Name) and value is not None: constants[target.id]=value
            if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute): pass
        # Judge prompt strings use .strip(), which literal_eval cannot evaluate.
        if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='strip' and isinstance(n.value.func.value,ast.Constant) and isinstance(n.value.func.value.value,str):
            for target in n.targets:
                if isinstance(target,ast.Name): constants[target.id]=n.value.func.value.value.strip()
    needed=set(roots);todo=list(roots)
    while todo:
        name=todo.pop()
        if name not in definitions: raise ValueError(f'missing upstream function {name}')
        for v in ast.walk(definitions[name]):
            if isinstance(v,ast.Name) and v.id in definitions and v.id not in needed and v.id!='_chat_answer':
                needed.add(v.id);todo.append(v.id)
    ns={'json':json,'re':re,'Any':Any,'Path':Path,**constants,**(external or {})}
    # Defaults are unchanged where defined upstream; these defaults are never used to retry.
    ns.setdefault('DEFAULT_API_MAX_RETRIES',0)
    ns.setdefault('DEFAULT_API_RETRY_BASE_DELAY_SEC',1.0)
    ns.setdefault('DEFAULT_API_RETRY_MAX_DELAY_SEC',1.0)
    ns['_chat_answer']=lambda *_a,**_k:_reply.get()
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in needed]
    text='from __future__ import annotations\n'+ '\n\n'.join(ast.get_source_segment(source,n) for n in selected)
    exec(compile(text,str(path),'exec'),ns)
    return ns

def load_evaluators():
    compat=_load(UPSTREAM/'_dataset_compat.py',['to_eval_row'])
    result={}
    base=_load(UPSTREAM/'_objective_base.py',['format_user_message_open_ended','generated_question_dict','reference_answer_from_row','preference_memory_from_row','reference_fact_basis_from_row','_extract_json_object','_coerce_binary_int'])
    obj=_load(UPSTREAM/'task_objective_fact_judgment.py',['objective_fact_judge_payload','judge_objective_fact_answer'],{'base':types.SimpleNamespace(**base)})
    result['objective_fact_judgment']={'prompt':obj['OBJECTIVE_FACT_JUDGE_PROMPT'],'payload':obj['objective_fact_judge_payload'],'parse':obj['judge_objective_fact_answer']}
    for task,prompt in [('contextual_scope_control','JUDGE_PROMPT'),('memory_evidence_conflict','JUDGE_PROMPT'),('valid_memory_selection','JUDGE_PREFRENCE_CHANGE_PROMPT'),('personalized_memory_use','JUDGE_RECOMMEND_PROMPT')]:
        ns=_load(UPSTREAM/f'task_{task}.py',['judge_user_payload','judge_answer'])
        result[task]={'prompt':ns[prompt],'payload':ns['judge_user_payload'],'parse':ns['judge_answer']}
    return compat['to_eval_row'],result

ADAPT,EVALUATORS=load_evaluators()

def judge_spec(task,row,answer):
    e=EVALUATORS[task]
    return e['prompt'],e['payload'](ADAPT(row),answer)

def parse_judge(task,row,answer,reply):
    token=_reply.set(reply)
    try:return EVALUATORS[task]['parse'](None,'gemini-3.5-flash',ADAPT(row),answer,max_retries=0)
    finally:_reply.reset(token)

def metric_map(task,score):
    if not score.get('judge_parse_ok'):return {'accuracy':None,'overuse':None,'underuse':None,'native_joint':None}
    if task=='objective_fact_judgment':a,o,u,j=score['objective_correctness'],score['preference_contamination'],None,score['suppress_pass']
    elif task=='contextual_scope_control':a,o,u,j=score['accuracy'],score['incorrectly_used_preference'],None,score['scope_pass']
    elif task=='memory_evidence_conflict':a,o,u,j=score['accuracy'],score['misled_by_conflicting_memory'],None,score['evidence_pass']
    elif task=='valid_memory_selection':a,o,u,j=score['uses_latest_preference'],score['outdated_preference_contamination'],1-score['uses_latest_preference'],score['valid_selection_pass']
    else:a,o,u,j=score['answer_accuracy'],None,1-score['preference_used'],score['memory_use_pass']
    return {'accuracy':a,'overuse':o,'underuse':u,'native_joint':int(j)}
