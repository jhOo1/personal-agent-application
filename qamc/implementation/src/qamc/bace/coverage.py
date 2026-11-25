"""Denominators over proposed use unions, not only the admitted score batch."""
from collections import Counter


PREFERENCE_USES={'PERSONAL_RANKING','PLAN_ADAPTATION','STYLE_ADAPTATION'}


def coverage_counts(scores):
    chosen=scores['inventory'];overflow=scores['unassessed_overflow']
    def key(x):return tuple(x[k] for k in ('unit_id','scope_id','use_kind'))
    chosen_keys={key(x) for x in chosen};overflow_keys={key(x) for x in overflow}
    if len(chosen_keys)!=len(chosen) or len(overflow_keys)!=len(overflow) or chosen_keys&overflow_keys:
        raise ValueError('Coverage requires distinct and disjoint use identities')
    assessed={role:{key(x) for x in scores['assessment'][role]['assessments'] if x['status']=='ASSESSED'}
              for role in ('allow','deny')}
    both=chosen_keys&assessed['allow']&assessed['deny']
    by_kind={kind:{'selected':sum(x['use_kind']==kind for x in chosen),
                   'overflow':sum(x['use_kind']==kind for x in overflow),
                   'both_assessed':sum(x[2]==kind for x in both)}
             for kind in sorted({x['use_kind'] for x in chosen+overflow})}
    pref_union={k for k in chosen_keys|overflow_keys if k[2] in PREFERENCE_USES}
    return {'selected':len(chosen),'overflow':len(overflow),'proposed_union':len(chosen)+len(overflow),
            'both_assessed':len(both),'preference_use_union':len(pref_union),
            'preference_uses_both_assessed':len(both&pref_union),
            'required_overflow':len(scores.get('required_overflow',[])),
            'by_use_kind':by_kind,
            'proposed_union_is_exhaustive_ground_truth':False,
            'fact_kind_is_model_prediction_not_verified_type':True}
