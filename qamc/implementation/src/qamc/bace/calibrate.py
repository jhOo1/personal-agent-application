"""Single, gated Platt fit with leave-one-source-root-out diagnostics; no API."""
import argparse
import json
from pathlib import Path
from .audit import OUT,digest,write_new
from .calibration_gate import qualification
from .metrics import binary_metrics


def fit_roles(rows,rules):
    """Use one fixed regularized sigmoid model, never search calibration families."""
    gate=qualification(rows,rules)
    if not gate['eligible']:
        return {'status':'INELIGIBLE','qualification':gate,'parameters':None}
    # Require a fully qualified input table; rejection must be resolved explicitly.
    if any(v['rejected'] for v in gate['roles'].values()):
        raise ValueError('Fit input must contain only qualified, distinct calibration uses')
    import numpy as np
    import sklearn
    from sklearn.linear_model import LogisticRegression
    parameters={};diagnostics={}
    def fit(part):
        model=LogisticRegression(C=1.0,solver='lbfgs',max_iter=1000,tol=1e-9)
        model.fit(np.array([[r['score']] for r in part]),[int(r['label']) for r in part])
        if model.n_iter_[0]>=1000:raise ValueError('Calibration optimizer did not converge')
        return model
    for role in ('allow','deny'):
        subset=[r for r in rows if r['role']==role];oof=[]
        for root in sorted({r['root'] for r in subset}):
            train=[r for r in subset if r['root']!=root]
            held=[r for r in subset if r['root']==root]
            model=fit(train)
            probabilities=model.predict_proba([[r['score']] for r in held])[:,1]
            oof.extend(dict(r,score=float(p)) for r,p in zip(held,probabilities))
        final=fit(subset)
        parameters[role]={'slope':float(final.coef_[0,0]),'intercept':float(final.intercept_[0])}
        diagnostics[role]={'raw':binary_metrics(subset),'root_held_out_sigmoid':binary_metrics(oof),
                           'oof_predictions':oof,'root_count':len({r['root'] for r in subset})}
    return {'status':'FIT_DEVELOPMENT_ONLY','qualification':gate,'parameters':parameters,
            'diagnostics':diagnostics,'method':'sigmoid_on_raw_score',
            'fixed_parameters':{'C':1.0,'solver':'lbfgs','max_iter':1000,'tol':1e-9},
            'sklearn_version':sklearn.__version__,'thresholds_selected':False,
            'held_out_test_claim':False,'ai_labels_are_exploratory':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['cal'],required=True)
    parser.add_argument('--labels',type=Path,required=True)
    parser.add_argument('--freeze-output',type=Path,required=True)
    args=parser.parse_args()
    rules=json.loads((OUT/'PHASE1_ANALYSIS_RULES.json').read_text())
    plan=json.loads((OUT/'SCORE_PILOT_PLAN.json').read_text())
    cases={c['uid']:c for c in plan['cases'] if c['phase']=='score-pilot'}
    rows=json.loads(args.labels.read_text())['records']
    # Root identity and source provenance come from the pre-dispatch manifest.
    for row in rows:
        case=cases.get(row.get('uid'))
        if case is None or row.get('root')!=case['source_root']:
            raise ValueError('Calibration row outside frozen new D_cal roots')
        if (row.get('source_review') or {}).get('source_hash')!=case['bundle_sha256']:
            raise ValueError('Source review must identify the frozen full input bundle hash')
    result=fit_roles(rows,rules)
    result.update(labels_sha256=digest(args.labels),plan_sha256=digest(OUT/'SCORE_PILOT_PLAN.json'),
                  rules_sha256=digest(OUT/'PHASE1_ANALYSIS_RULES.json'),new_model_requests=0)
    write_new(args.freeze_output,result)
    print(json.dumps({'status':result['status'],'new_model_requests':0}))


if __name__=='__main__':main()
