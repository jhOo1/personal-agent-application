"""Post-freeze identity ablation: routing reads public Actor inputs only."""
from copy import deepcopy
import json
from .actor_use_window_v2 import TYPE_NOTICE

BASE_FIELDS=('query','current_context','facts','source_evidence')
ALLOWED=set(BASE_FIELDS)|{'source_kind_annotations','annotation_notice'}


def payload(request):
    if request is None:return None
    messages=request['messages']
    if len(messages)!=2 or [m['role'] for m in messages]!=['system','user']:
        raise ValueError('Identity guard requires the frozen two-message Actor interface')
    value=json.loads(messages[1]['content'])
    if not isinstance(value,dict) or not all(k in value for k in BASE_FIELDS):
        raise ValueError('Actor input lacks explicit base fields')
    return value


def empty_evidence(value):
    # Unknown fields may carry facts. Missing or malformed content is never
    # treated as evidence of emptiness, and no label or task ID is consulted.
    return (value is not None and not set(value)-ALLOWED
        and isinstance(value['query'],str) and bool(value['query'].strip())
        and isinstance(value['current_context'],str) and not value['current_context'].strip()
        and value['facts']==[] and value['source_evidence']==[]
        and value.get('source_kind_annotations',[])==[]
        and value.get('annotation_notice',TYPE_NOTICE)==TYPE_NOTICE)


def compile_identity(original_request, candidate_request):
    if original_request is None or candidate_request is None:
        return deepcopy(candidate_request),'BASE_OR_CANDIDATE_REQUEST_UNAVAILABLE'
    original,candidate=payload(original_request),payload(candidate_request)
    if any(original[k]!=candidate[k] for k in BASE_FIELDS):
        raise ValueError('Frozen base input differs across candidate and baseline')
    for key in ('model','temperature','max_tokens','stream','stream_options'):
        if original_request[key]!=candidate_request[key]:
            raise ValueError('Actor wire configuration differs')
    if empty_evidence(original) and empty_evidence(candidate):
        return deepcopy(original_request),'EMPTY_EVIDENCE_BASELINE_IDENTITY'
    return deepcopy(candidate_request),'UNCHANGED_NONEMPTY_OR_UNCERTAIN_INPUT'
