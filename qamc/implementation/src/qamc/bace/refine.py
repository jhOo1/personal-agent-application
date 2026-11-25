"""One proposal and one bilateral verification round, never a free debate."""
from .contract import UseKey,Span


def validate_narrowing(proposal,original,units,scope_ids):
    if proposal.get('status')=='UNRESOLVED':return proposal
    if proposal.get('status')!='PROPOSED':raise ValueError('Invalid refinement status')
    key=UseKey(**proposal['use_key'])
    if key.unit_id!=original.unit_id or key.scope_id not in scope_ids:
        raise ValueError('Refinement cannot invent memory or scope')
    if not isinstance(proposal.get('boundary'),str) or not 1<=len(proposal['boundary'])<=500:
        raise ValueError('Explicit bounded use restriction required')
    if not proposal.get('source_spans'):raise ValueError('Refinement must retain source proof')
    for span in proposal['source_spans']:Span(**span).validate(units)
    # Structural checks are necessary; two role checks assess semantic narrowing.
    return proposal


def bounded_refine(steps,identity,original,inputs,propose,verify_allow,verify_deny):
    proposal=steps.run(identity+'/refine',inputs,propose)
    if proposal.get('status')=='UNRESOLVED':
        return {'attempted':True,'accepted':False,'proposal':proposal,'reason':'UNRESOLVED','verification_rounds':0}
    checks=[]
    for role,check in (('allow',verify_allow),('deny',verify_deny)):
        checks.append(steps.run(identity+'/verify/'+role,{'original':original,'proposal':proposal},lambda check=check:check(proposal)))
    accepted=all(c.get('status')=='ASSESSED' and c.get('accept') is True for c in checks)
    return {'attempted':True,'accepted':accepted,'proposal':proposal,'checks':checks,
            'reason':'BILATERALLY_VALIDATED' if accepted else 'UNRESOLVED','verification_rounds':1}
