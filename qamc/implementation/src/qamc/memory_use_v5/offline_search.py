"""Small deterministic policy-candidate ledger; no model or final-set access."""
import copy,re
from .policy_cards import assert_training_allowed
OPS={'ADD_CARD','EDIT_ONE_CARD','NARROW_TRIGGER','EXPAND_TRIGGER_WITH_EVIDENCE','ADD_EXCEPTION','MERGE_REDUNDANT_CARDS','RETIRE_CARD'}
def propose(library, operation, card, *, split, round_number, candidate_number):
    assert_training_allowed(split)
    if split=='D_select':raise ValueError('selection feedback cannot generate proposals')
    if operation not in OPS or not 1<=round_number<=3 or not 1<=candidate_number<=4:raise ValueError('search opportunity exceeded')
    if not isinstance(card,dict) or not isinstance(card.get('policy_id'),str):raise ValueError('invalid card')
    text=card.get('instruction','')
    if not isinstance(text,str) or not text.strip() or re.search(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b(?:memsyco|personamem|benchpres)\b',text,re.I):raise ValueError('disallowed policy content')
    if card.get('status')!='PROPOSED':raise ValueError('new policy must be proposed before validation')
    new=copy.deepcopy(library)
    if operation=='ADD_CARD':
        if any(x['policy_id']==card['policy_id'] for x in new):raise ValueError('duplicate policy')
        new.append(copy.deepcopy(card))
    elif operation=='RETIRE_CARD':
        old=next((x for x in new if x['policy_id']==card['policy_id']),None)
        if old is None:raise ValueError('unknown policy')
        old['status']='RETIRED'
    else:
        raise NotImplementedError('operation requires explicit audited implementation')
    if len([x for x in new if x.get('status')!='RETIRED'])>12:raise ValueError('library limit exceeded')
    return new

def promote(card, *, target_pass, preservation_pass, boundary_pass, selection_pass):
    if card.get('status')!='PROPOSED' or not all((target_pass,preservation_pass,boundary_pass,selection_pass)):
        raise ValueError('candidate cannot be promoted')
    return {**card,'status':'VALIDATED'}
