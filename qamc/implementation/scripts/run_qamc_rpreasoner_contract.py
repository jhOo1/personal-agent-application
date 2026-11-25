#!/usr/bin/env python3
"""Reuse the baseline runner in an isolated cardinality-adaptation namespace."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import run_qamc_rpreasoner as runner
from proposals.qamc_rpreasoner_contract.engine import CardinalityRPReasonerEngine
from qamc.pa.prepare import write_once
OUT=ROOT/'reports/qamc_rpreasoner_contract'
RUN=ROOT/'runs/qamc_rpreasoner_contract/execution'

def configure():
    runner.OUT=OUT;runner.RUN=RUN;runner.RPReasonerEngine=CardinalityRPReasonerEngine

def freeze():
    old=ROOT/'reports/qamc_rpreasoner'
    plan=runner.read(old/'PLAN.json')
    plan.update(adaptation='multi_persona_explicit_output_count_v1',
                parent_plan=str((old/'PLAN.json').relative_to(ROOT)),
                no_failed_payload_retry=True, single_persona_prompt_unchanged=True)
    paths=[Path(__file__),ROOT/'proposals/qamc_rpreasoner_contract/engine.py',old/'PLAN.json',
           OUT/'DECISION_RULES.md',ROOT/'scripts/diagnose_qamc_rpreasoner.py']
    plan['frozen_files'].update({str(p.relative_to(ROOT)):runner.filehash(p) for p in paths})
    policy=runner.read(old/'DISPATCH_POLICY.json');policy['epoch_id']='qamc_rpreasoner_contract_20261107_01'
    for name in ['TEMPLATES.json','CONTROL_IMPORTS.json']:write_once(OUT/name,runner.read(old/name))
    write_once(OUT/'DISPATCH_POLICY.json',policy);write_once(OUT/'PLAN.json',plan)
    return plan

def main():
    configure()
    if len(sys.argv)==2 and sys.argv[1]=='freeze':
        print(json.dumps({'cases':len(freeze()['cases']),'new_calls':0}));return
    runner.main()
if __name__=='__main__':main()
