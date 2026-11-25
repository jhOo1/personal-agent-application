"""Resolve an unambiguous legacy memory ID to a visible profile candidate ID."""


def resolve_candidate_aliases(result, entries_key, candidates):
    """Mutate only unknown candidate IDs with a unique provenance-compatible alias.

    An existing candidate ID is never rewritten. Ambiguous or unlinked aliases
    remain unchanged and must fail the normal validator. The original model
    response remains in the gateway ledger; corrections are returned for audit.
    """
    known={c['id'] for c in candidates}
    corrections=[]
    entries=result.get(entries_key)
    if not isinstance(entries,list):return corrections
    for index,item in enumerate(entries):
        if not isinstance(item,dict):continue
        alias=item.get('candidate_id')
        if not isinstance(alias,str) or alias in known:continue
        source_ids={span.get('source_id') for span in (item.get('spans') or []) if isinstance(span,dict)}
        matches=[c for c in candidates if c.get('metadata',{}).get('memory_id')==alias and
                 (not source_ids or source_ids <= set(c.get('source_ids',[])))]
        if len(matches)==1:
            item['candidate_id']=matches[0]['id']
            corrections.append({'entry_index':index,'from':alias,'to':matches[0]['id']})
    return corrections
