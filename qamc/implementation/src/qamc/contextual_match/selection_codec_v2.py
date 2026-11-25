"""Uniform lexical compatibility, with no new semantic selection decisions."""
from copy import deepcopy
import json
from qamc.common import parse_object,sha
from . import behavioral_probes

POLICY='selection_action_spelling_v2'
ALIASES={'APPLIED':'APPLY','DROPPED':'DROP'}


def actor(task,raw,prompts):
    obj=deepcopy(parse_object(raw));changes=[]
    actions=obj.get('preference_actions')
    if isinstance(actions,list):
        for row in actions:
            if isinstance(row,dict) and isinstance(row.get('decision'),str) and row['decision'] in ALIASES:
                old=row['decision'];row['decision']=ALIASES[old]
                changes.append({'memory_id':row.get('memory_id'),'from':old,'to':row['decision']})
    normalized=json.dumps(obj,ensure_ascii=False)
    # The old validator still rejects unknown IDs, missing rows, contradictory
    # notes and illegal spans. Never fill missing actions or repair semantics.
    built=behavioral_probes.actor(task,normalized,prompts)
    return {**built,'codec_audit':{'policy':POLICY,'raw_selector_sha256':sha(raw),
        'normalized_selector':obj,'changes':changes,'new_semantic_decisions':False}}
