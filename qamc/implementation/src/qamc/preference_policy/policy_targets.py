"""Admissible feedback targets, separate from unchanged published score tables.

A fixed-option task cannot edit a source claim inside the unique natively correct
option. A source Judge disagreeing with that option needs evaluator calibration,
not repeated sampling of alternate formatting of the same letter.
"""
ISSUES=('unsupported_personal_facts','overuse','underuse')


def eligible_target(experience):
    score=experience.get('feedback',{}).get('score',{})
    if score.get('metric')=='official_option_parser_accuracy':
        return score.get('accuracy')==0
    diagnostic=experience.get('source_feedback',{}).get('diagnostic',{})
    return score.get('accuracy')==0 or any(diagnostic.get(k)for k in ISSUES)


def semantic_quality_gain(parent,candidate):
    if parent.get('source_diagnostic',{}).get('status')!='ok'or candidate.get('source_diagnostic',{}).get('status')!='ok':return False
    ps,cs=parent.get('score')or{},candidate.get('score')or{}
    if ps.get('metric')=='official_option_parser_accuracy':
        a,b=ps.get('extracted',[]),cs.get('extracted',[])
        if len(a)!=1 or len(b)!=1 or a==b:return False
    p=parent['source_diagnostic']['diagnostic'];c=candidate['source_diagnostic']['diagnostic']
    return any(len(c[k])<len(p[k])for k in ISSUES)
