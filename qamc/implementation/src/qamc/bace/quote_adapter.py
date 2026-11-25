"""Restore Unicode space glyphs from exact offsets without altering source data.

Only equal-length Zs-space substitutions are recoverable. Words, punctuation,
offsets, source identity, newline structure and scores never change. Original
responses and earlier validation failures remain in the transport ledger.
"""
from copy import deepcopy
import unicodedata


def space_key(text):
    return ''.join(' ' if unicodedata.category(c)=='Zs' else c for c in text)


def restore_space_quotes(obj,units):
    result=deepcopy(obj);changes=[]
    def visit(value,path):
        if isinstance(value,dict):
            if {'unit_id','start','end','exact_quote'}<=set(value):
                uid=value['unit_id'];start=value['start'];end=value['end'];quote=value['exact_quote']
                if uid in units and type(start) is int and type(end) is int and isinstance(quote,str):
                    text=units[uid]['exact_text']
                    if 0<=start<end<=len(text):
                        expected=text[start:end]
                        if quote!=expected and len(quote)==len(expected) and space_key(quote)==space_key(expected):
                            changes.append({'json_path':path,'unit_id':uid,'start':start,'end':end,
                                'original_quote':quote,'restored_quote':expected,'reason':'equal_length_unicode_Zs_space_only'})
                            value['exact_quote']=expected
            for k,v in value.items():visit(v,path+'/'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):visit(v,path+'/'+str(i))
    visit(result,'')
    return result,changes


class QuoteGateway:
    def __init__(self,base):self.base=base
    def __getattr__(self,name):return getattr(self.base,name)
    def object(self,key,prompt,payload,validator=None,max_tokens=4096):
        units={u['unit_id']:u for u in payload.get('input',{}).get('units',[])}
        def check(obj):
            restored,changes=restore_space_quotes(obj,units)
            if validator:validator(restored)
            if changes:
                self.base.event(key=key,status='source_unicode_space_restored',changes=changes,
                                original_response_preserved=True,semantic_repair=False)
                obj.clear();obj.update(restored)
        return self.base.object(key,prompt,payload,check,max_tokens)
