"""Public-only requests and decoders for the frozen representation experiment.

Dataset identity, author labels and native grading remain in the runner's
evaluation layer. The same method functions are used for every PublicTask.
"""
import json
from .core import normalize_selection, validate_task_view
from .prompts import request
from .representation_replay import recover_memory_view
from qamc.common import parse_object
from qamc.pa.core import compile_view

METHODS=("R0","R1","R2","R3","RAW","QUERY_SUMMARY","INCREMENTAL_UNIFIED_ADAPT")


def text_request(system, payload, model="qwen3.8-flash", cap=8192):
    return {"model":model,"messages":[{"role":"system","content":system},
        {"role":"user","content":payload if isinstance(payload,str) else json.dumps(payload,ensure_ascii=False)}],
        "temperature":0,"max_tokens":cap,"stream":True,"stream_options":{"include_usage":True}}


def incremental_request(task, prompt_factory, incremental_clause):
    # The author explicit input is used as a common public container, including
    # dialogue text where supplied. This is an adaptation, not the implicit
    # author evaluation track. No benchmark name or gold controls this choice.
    track="explicit/single" if len(task.memories)==1 else "explicit/multi"
    body=prompt_factory(task,track,"style_intent")
    user=body["messages"][-1]["content"]+"\n\n"+incremental_clause
    if task.current_context or task.fixed_facts:
        user+="\n\nAdditional public current context and shared facts:\n"+json.dumps(
            {"current_context":task.current_context,"fixed_facts":list(task.fixed_facts)},ensure_ascii=False)
    return text_request(body["messages"][0]["content"],user,cap=8192)


def read_request(task,method,prompts,memory=None,task_view=None,incremental=None):
    if method=="RAW":return None
    if method=="QUERY_SUMMARY":return text_request(prompts["summary"],task.payload())
    if method=="INCREMENTAL_UNIFIED_ADAPT":
        if incremental is None:raise ValueError("Frozen Incremental request required")
        return incremental
    if method not in METHODS:raise ValueError("Unknown development method")
    return request("Selector",task,"qwen3.8-flash",8192,prompts["style_selector"],method,memory,task_view)


def decode_representation(task,stage,answer):
    obj=parse_object(answer)
    if stage=="Memory":return recover_memory_view(task,obj)
    if stage=="Task":return {"view":validate_task_view(task,obj),"events":[]}
    if stage=="MemorySummary":
        if not isinstance(obj,dict) or set(obj)!={"summary"} or not isinstance(obj["summary"],str) or not obj["summary"].strip():
            raise ValueError("Invalid strong memory summary envelope")
        return {"view":obj,"events":[]}
    raise ValueError("Unknown representation phase")


def actor_request(task,method,answer,prompts):
    if method=="RAW":
        selection={"preference_actions":[{"memory_id":m.memory_id,"decision":"APPLY"} for m in task.memories],"unresolved_ids":[]}
        view=compile_view(task,normalize_selection(task,selection),"V1")
    elif method=="QUERY_SUMMARY":
        if not isinstance(answer,str) or not answer.strip():raise ValueError("Empty query-aware summary")
        view={"query":task.query,"current_context":task.current_context,"facts":list(task.fixed_facts),
              "query_aware_summary":answer}
    elif method=="INCREMENTAL_UNIFIED_ADAPT":
        value=parse_object(answer);policy=value.get("policy")
        if not isinstance(policy,str):raise ValueError("Missing Incremental policy")
        policy=policy.strip()
        if len(policy)!=len(task.memories) or set(policy)-set("ABC"):raise ValueError("Invalid Incremental policy alignment")
        selection={"preference_actions":[{"memory_id":m.memory_id,"decision":"DROP" if label=="A" else "APPLY"}
                   for m,label in zip(task.memories,policy,strict=True)],"unresolved_ids":[]}
        view=compile_view(task,normalize_selection(task,selection),"V1")
    else:
        view=compile_view(task,normalize_selection(task,parse_object(answer)),"V1")
    return {"view":view,"request":text_request(prompts["actor"],view,cap=4096)}
