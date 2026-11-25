"""Offline, lossless normalization of a redundant source-unit hash suffix.

Only an exact source-id/start/end match with ONE provided unit may normalize.
Offsets, text, scope, purpose, rationale and choices are never inferred or edited.
"""
from copy import deepcopy
from .core import validate_joint,validate_role,validate_resolution,fields,strings


def normalize_hash_suffix(obj,payload):
    units={u['unit_id']for u in payload['units']};prefix={}
    for uid in units:prefix.setdefault(uid.rsplit(':',1)[0],[]).append(uid)
    fixes=[]
    def resolve(value):
        if value in units:return value
        matches=prefix.get(value.rsplit(':',1)[0],[])
        if len(matches)==1:
            fixes.append({'original':value,'canonical':matches[0],'basis':'unique exact source_id/start/end; suffix only'})
            return matches[0]
        return value
    def visit(value):
        if isinstance(value,dict):
            out={}
            for k,v in value.items():
                if k=='unit_id'and isinstance(v,str):out[k]=resolve(v)
                elif k in {'source_refs','selected_unit_ids','task_unit_ids','shared_constraint_refs'}and isinstance(v,list):out[k]=[resolve(x)if isinstance(x,str)else x for x in v]
                else:out[k]=visit(v)
            return out
        if isinstance(value,list):return [visit(v)for v in value]
        return value
    return visit(deepcopy(obj)),fixes


def validate_saved(module,obj,payload,scope,merged=None):
    if module=='gate':
        fields(obj,'selected_unit_ids material_gaps')
        if not set(strings(obj['selected_unit_ids']))<={u['unit_id']for u in payload['units']}:raise ValueError('unknown gate source after replay')
        strings(obj['material_gaps']);return obj
    if module in {'joint','recheck'}:return validate_joint(obj,payload,scope)
    if module in {'allow','deny'}:return validate_role(obj,payload,scope,module)
    if module=='resolution':return validate_resolution(obj,merged,payload,scope)
    raise ValueError('unsupported saved module')
