"""Released all-memory policy with the candidate's identical public container."""
import json
from . import gepa_unified


def actor(task, bridge):
    built=gepa_unified.actor(task,bridge)
    user={'query':task.query,'current_context':task.current_context,'fixed_facts':list(task.fixed_facts)}
    built['request']['messages'][1]['content']=json.dumps(user,ensure_ascii=False)
    built['audit']['public_container_always_json']=True
    return built
