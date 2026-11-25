"""Offline score-blinded source-use review material; not an automatic labeler."""
import argparse
import json
from .audit import ROOT,OUT,digest
from .prepare import RUN
from .evaluation_roots import evaluation_root
from qamc.common import sha
from qamc.transport_helpers import atomic_json


def case_pack(case,bundle,scores):
    """Only original inputs and proposed use identity enter review material.

    Reviewer never sees role scores, role rationales or method outcomes. This
    is score blinding, not proof that source selection itself is unbiased.
    """
    units={u['unit_id']:u for u in bundle['payload']['units']}
    records=[]
    for use in scores['inventory']:
        key=[use[k] for k in ('unit_id','scope_id','use_kind')]
        records.append({'review_id':sha([case['uid'],key])[:24],
                        'use_key':key,'source_unit':units[use['unit_id']],
                        'query_anchor':use['query_anchor'],'source_spans':use['source_spans'],
                        'beneficial':None,'inappropriate_use':None,
                        'beneficial_only_if_limited':None,'unresolved':True,
                        'source_review':None})
    return {'uid':case['uid'],'phase':case['phase'],'root':evaluation_root(case,bundle),
            'frozen_manifest_source_root':case['source_root'],
            'source_hash':case['bundle_sha256'],'original_input':bundle['payload'],
            'scopes':case['scopes'],'items':records,
            'unassessed_overflow':scores['unassessed_overflow'],
            'required_overflow':scores.get('required_overflow',[])}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--namespace',choices=['original','quote_space_v2','anchored_span_v3'],required=True)
    args=parser.parse_args()
    root=RUN if args.namespace=='original' else RUN/args.namespace
    plan=json.loads((OUT/'SCORE_PILOT_PLAN.json').read_text());cases=[]
    for case in plan['cases']:
        path=root/'cases'/sha(case['uid'])[:24]/'scores.json'
        if not path.exists():continue
        bundle_path=ROOT/case['bundle']
        if digest(bundle_path)!=case['bundle_sha256']:raise ValueError('Frozen source drift')
        cases.append(case_pack(case,json.loads(bundle_path.read_text()),json.loads(path.read_text())))
    suffix={'original':'','quote_space_v2':'_V2','anchored_span_v3':'_V3'}[args.namespace]
    atomic_json(OUT/('SOURCE_USE_REVIEW_PACK'+suffix+'.json'),{
        'namespace':args.namespace,'role_scores_blinded':True,'human_review':0,
        'new_model_requests':0,'labels_supplied':0,'cases':cases,
        'warning':'Selection is model-proposed; source review must evaluate both events independently. Unknown is not negative. No inference-module input may read this pack.'})
    print(json.dumps({'cases':len(cases),'uses':sum(len(c['items']) for c in cases),'labels_supplied':0}))


if __name__=='__main__':main()
