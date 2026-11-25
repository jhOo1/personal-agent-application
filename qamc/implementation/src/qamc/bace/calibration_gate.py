"""Offline eligibility checks; benchmark proxies never silently become UseGold."""
from .metrics import binary_metrics


def qualification(rows, rules):
    """Check each role separately, retaining all unknown and unqualified records.

    A separate source review supplies qualification, not the scored role's own
    rationale. These fields document provenance; they do not certify semantics.
    """
    output={}
    for role in ('allow','deny'):
        candidates=[r for r in rows if r.get('role')==role]
        qualified=[];rejected=[];seen=set()
        for row in candidates:
            reasons=[]
            use=row.get('use_key')
            identity=(row.get('uid'),tuple(use)) if isinstance(use,list) else None
            if identity is None or not identity[0] or len(identity[1])!=3:
                reasons.append('missing_use_identity')
            elif identity in seen:reasons.append('duplicate_use_label')
            else:seen.add(identity)
            if row.get('phase')!='score-pilot':reasons.append('not_new_D_cal')
            if row.get('status')!='ASSESSED':reasons.append('not_assessed')
            if type(row.get('label')) is not bool:reasons.append('unknown_binary_label')
            if row.get('calibration_qualified') is not True:reasons.append('not_source_qualified')
            review=row.get('source_review') or {}
            if not review.get('record_id') or not review.get('source_hash'):
                reasons.append('missing_source_review_provenance')
            if review.get('independent_of_role_score') is not True:
                reasons.append('not_independent_of_scored_role')
            if review.get('review_kind') not in {'human','ai_exploratory'}:
                reasons.append('undeclared_review_kind')
            if not row.get('root'):reasons.append('missing_root')
            if reasons:rejected.append({'review_id':row.get('review_id'),'reasons':reasons})
            else:qualified.append(row)
        metrics=binary_metrics(qualified)
        failures=[]
        minimum=rules['calibration_minimum']
        for key,limit in [('positives','known_positive_per_role'),('negatives','known_negative_per_role'),('roots','distinct_roots')]:
            if metrics[key]<minimum[limit]:failures.append('insufficient_'+key)
        if metrics['auroc'] is None or metrics['auroc']<=.5:
            failures.append('positive_rank_discrimination_not_established')
        # Every leave-one-root-out fit needs both classes in its training roots.
        roots={r['root'] for r in qualified}
        for root in roots:
            labels={r['label'] for r in qualified if r['root']!=root}
            if labels!={True,False}:
                failures.append('root_holdout_training_class_degeneracy');break
        output[role]={'eligible':not failures,'failures':failures,'metrics':metrics,
                      'rejected':rejected,'qualified_count':len(qualified),
                      'ai_review_count':sum(r['source_review']['review_kind']=='ai_exploratory' for r in qualified),
                      'human_review_count':sum(r['source_review']['review_kind']=='human' for r in qualified)}
    return {'eligible':all(v['eligible'] for v in output.values()),'roles':output,
            'provenance_checks_are_not_semantic_certification':True}
