#!/usr/bin/env python3
"""Explicit post-smoke availability amendment; never relabels smoke as passed."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import run_qamc_rpreasoner as base
import run_qamc_rpreasoner_contract as current
from qamc.pa.prepare import write_once
from qamc.common import parse_object
from qamc.pa.rpeval_scoring import parse_score
AMEND=current.OUT/'UNISSUED_CONTINUATION.json'

def acceptance(plan):
    rows=[r for r in base.outcomes() if r['uid'] in plan['smoke_uids']]
    if len(rows)!=4 or any(r['pipeline_status']!='OK' or r['answer_status']!='OK' for r in rows):
        raise ValueError('Require all four successful smoke generations')
    by_uid={}
    for r in rows:
        if r['uid'] in by_uid and by_uid[r['uid']]!=r['selection']:raise ValueError('Prediction mismatch')
        by_uid[r['uid']]=r['selection']
    # The only permitted incomplete score is the already observed missing overall
    # Judge field. Check all other fields with the existing strict validator, but
    # never export the temporary validation sentinel as an actual score.
    failed=[r for r in rows if r['score_status']!='OK']
    if len(failed)!=1 or failed[0]['arm']!='RP_PAPER_ADAPTED' or failed[0].get('score_error')!='Invalid severity: Judge':
        raise ValueError('Unreviewed score failure; amendment does not apply')
    response=current.RUN/'api/raw/000004_response.json'
    raw=parse_object(base.read(response)['answer'])
    if 'Judge' in raw:raise ValueError('Unexpected score contract')
    count=len(failed[0]['selection']['memory_ids'])
    parse_score({**raw,'Judge':0},count,True)  # Validation only; original missing remains missing.
    return {'saved_generation_cells':4,'strict_valid_scores':3,'partial_scores':1,
            'partial_score_response_sha256':base.filehash(response),'temporary_validation_value_exported':False}

def audit():
    current.configure();plan=base.read(current.OUT/'PLAN.json');base.check(plan)
    state=acceptance(plan)
    remaining=[c for c in plan['cases'] if c['uid'] not in plan['smoke_uids']]
    paths=[Path(__file__),current.OUT/'PLAN.json',current.OUT/'SMOKE_ACCEPTANCE.json',
           current.OUT/'PARTIAL_SCORE_DIAGNOSTIC.json']
    record={'version':'auxiliary_score_availability_amendment_v1','post_smoke_amendment':True,
            'original_smoke_passed':False,'reason':'Do not block successful end-to-end generation solely on an absent overall Judge scalar. Retain strict score missingness and all partial values separately.',
            'scope':'Only six previously undispatched roots from the same frozen eight-root manifest.',
            'semantic_prompt_changes':False,'scoring_prompt_changes':False,'failed_request_retries':False,
            'completed_cell_regeneration':False,'new_samples':False,'new_request_quota':None,
            'nominal_remaining_calls_before_cache':36,'shared_existing_stage_attempt_guard':plan['request_cap'],
            'unissued_uids':[c['uid'] for c in remaining],'acceptance':state,
            'frozen_amendment_files':{str(p.relative_to(ROOT)):base.filehash(p) for p in paths}}
    return plan,remaining,record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','run']);args=parser.parse_args()
    plan,cases,record=audit()
    if args.action=='freeze':write_once(AMEND,record);print(json.dumps(record));return
    if base.read(AMEND)!=record:raise ValueError('Amendment drift')
    base.execute(plan,cases)
if __name__=='__main__':main()
