"""Evaluation-only clusters; never rewrite the frozen inference manifest."""


def evaluation_root(case,bundle):
    if case['phase']=='regression' and case['uid'].startswith('benchpres/'):
        # Original source_family was context-specific; the full profile source
        # hash is shared across contexts and matches the prior profile audit.
        root=bundle.get('source_hash')
        if not isinstance(root,str) or not root:
            raise ValueError('Old BenchPreS regression requires full-profile source hash')
        return root
    return case['source_root']
