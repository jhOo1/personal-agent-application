"""Explicit, versioned deterministic recovery of mechanical annotation fields.

Original outputs are never overwritten. This is not evidence that the recovered
attributes are semantically correct. A missing/nonunique quote is not repaired.
"""
from copy import deepcopy
from qamc.common import sha
from .core import ContractError, source_map, validate_memory_view, validate_ref

VERSION="program_bound_identity_full_span_alias_unique_quote_v3"


def recover_memory_view(task, original):
    value=deepcopy(original);events=[];sources=source_map(task,"memory")
    if not isinstance(value,dict) or not isinstance(value.get("sources"),list):
        raise ContractError("No complete MemoryView object to replay")
    # A sole full-source span has exactly the same identity boundary as its
    # parent source. Never guess aliases for unknown IDs or partial spans.
    aliases={span_id:m.memory_id for m in task.memories for span_id,text in m.spans().items()
             if len(m.spans())==1 and text==m.text}
    for row in value["sources"]:
        if isinstance(row,dict) and row.get("source_id") in aliases:
            old=row["source_id"];row["source_id"]=aliases[old]
            events.append({"kind":"FULL_SOURCE_SPAN_ID_ALIAS","old_id":old,"source_id":row["source_id"]})
    ids=[r.get("source_id") for r in value["sources"] if isinstance(r,dict)]
    if len(ids)!=len(value["sources"]) or len(set(ids))!=len(ids) or set(ids)!=set(sources):
        raise ContractError("Cannot recover missing, duplicate or invented source identity")
    for row in value["sources"]:
        sid=row["source_id"];expected=sha(sources[sid])
        if row.get("source_sha256")!=expected:
            events.append({"kind":"PROGRAM_BOUND_SOURCE_HASH","source_id":sid,
                           "old_value":row.get("source_sha256"),"new_value":expected})
            row["source_sha256"]=expected
        fields=[row.get("subject"),row.get("content_kind")]
        for key in ("properties","observed_context","explicit_scope","relations"):
            if not isinstance(row.get(key),list):raise ContractError("Malformed attribute list")
            fields+=row[key]
        for field in fields:
            if not isinstance(field,dict) or not isinstance(field.get("evidence"),list):
                raise ContractError("Malformed attributed field")
            for ref in field["evidence"]:
                if isinstance(ref,dict) and ref.get("source_id") in aliases:
                    old=ref["source_id"];ref["source_id"]=aliases[old]
                    events.append({"kind":"FULL_SOURCE_SPAN_REFERENCE_ALIAS","old_id":old,"source_id":ref["source_id"]})
                try:
                    validate_ref(ref,sources);continue
                except ContractError:
                    pass
                if not isinstance(ref,dict) or set(ref)!={"source_id","start","end","quote"}:
                    raise ContractError("Malformed quote reference")
                rsid,quote=ref["source_id"],ref["quote"]
                if rsid not in sources or not isinstance(quote,str) or not quote:
                    raise ContractError("Cannot recover unknown source or empty quote")
                text=sources[rsid];start=text.find(quote)
                if start<0 or text.find(quote,start+1)>=0:
                    raise ContractError("Quote is absent or ambiguous; no semantic rewrite")
                events.append({"kind":"UNIQUE_EXACT_QUOTE_OFFSET","source_id":rsid,
                               "old_start":ref["start"],"old_end":ref["end"],
                               "new_start":start,"new_end":start+len(quote)})
                ref.update(start=start,end=start+len(quote))
    validate_memory_view(task,value)
    return {"version":VERSION,"view":value,"events":events,
            "original_sha256":sha(original),"recovered_sha256":sha(value),
            "semantic_rewrite":False,"gold_used":False}
