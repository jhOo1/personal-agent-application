"""Eligibility gate for source-supported development feedback."""
TYPES={'SELECTION','STATE','USE','FORMAT','EVALUATION','UPSTREAM','UNKNOWN'}
QUALITIES={'NATIVE_DETERMINISTIC','SOURCE_CHECKED','AUTO_SEMANTIC','DISPUTED'}
def build_packet(*, split, first_visible_failure, observable_claim, source_refs, counterevidence_refs, feedback_quality, attribution_status):
    if split not in {'D_regression','D_opt'}: raise ValueError('policy feedback may use only training or regression data')
    if first_visible_failure not in TYPES or feedback_quality not in QUALITIES: raise ValueError('invalid feedback type')
    if attribution_status not in {'OBSERVED_PATH','HYPOTHESIS','INTERVENTION_SUPPORTED'}: raise ValueError('invalid attribution status')
    if not isinstance(observable_claim,str) or not observable_claim.strip(): raise ValueError('missing observation')
    refs=list(source_refs);counter=list(counterevidence_refs)
    eligible=bool(refs) and feedback_quality in {'SOURCE_CHECKED','NATIVE_DETERMINISTIC'} and first_visible_failure in {'STATE','USE'}
    return {'split':split,'first_visible_failure':first_visible_failure,'observable_claim':observable_claim,'source_refs':refs,'counterevidence_refs':counter,'feedback_quality':feedback_quality,'attribution_status':attribution_status,'eligible_for_policy_update':eligible}
