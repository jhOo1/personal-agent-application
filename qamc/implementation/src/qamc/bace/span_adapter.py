"""Restore an end offset only when the exact quote proves its anchored range.

No search for a different unit or start is allowed. Original quotes, offsets,
failures and repair responses remain in the ledger. This does not decide scope
or whether the chosen quotation retains enough semantic context.
"""
from copy import deepcopy
from .quote_adapter import restore_space_quotes


def restore_anchored_ends(obj,units):
    result,changes=restore_space_quotes(obj,units)
    def visit(value,path):
        if isinstance(value,dict):
            if {'unit_id','start','end','exact_quote'}<=set(value):
                uid=value['unit_id'];start=value['start'];end=value['end'];quote=value['exact_quote']
                if uid in units and type(start) is int and type(end) is int and isinstance(quote,str) and quote:
                    text=units[uid]['exact_text'];derived=start+len(quote)
                    # End is redundant when an unchanged quote exactly matches at
                    # its unchanged declared start. Never repair words or relocate.
                    if 0<=start<derived<=len(text) and derived!=end and text[start:derived]==quote:
                        changes.append({'json_path':path,'unit_id':uid,'start':start,
                                        'original_end':end,'restored_end':derived,
                                        'exact_quote':quote,'reason':'exact_quote_at_unchanged_start'})
                        value['end']=derived
            for k,v in value.items():visit(v,path+'/'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):visit(v,path+'/'+str(i))
    visit(result,'')
    return result,changes


class SpanGateway:
    """Apply only offline-tested source representation recovery before validation."""
    def __init__(self,base):self.base=base
    def __getattr__(self,name):return getattr(self.base,name)
    def object(self,key,prompt,payload,validator=None,max_tokens=4096):
        units={u['unit_id']:u for u in payload.get('input',{}).get('units',[])}
        def check(obj):
            restored,changes=restore_anchored_ends(obj,units)
            if validator:validator(restored)
            if changes:
                self.base.event(key=key,status='anchored_source_span_restored',changes=changes,
                                original_response_preserved=True,semantic_repair=False)
                obj.clear();obj.update(restored)
        return self.base.object(key,prompt,payload,check,max_tokens)
