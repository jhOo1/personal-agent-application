"""Frozen stage plan, preflight and dispatch. Offline commands never call models."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from .prepare import ROOT,OUT,RUN,write_once
from .smoke import prepare_smoke
from .experiment import Experiment,load_task
from .gateway import StageGateway,validate_service_authorization
from .report import build_report
from qamc.bace.runtime import runner_lock
from qamc.common import sha

STAGE_RUN=RUN/'smoke_execution'
PLAN=OUT/'SMOKE_PLAN.json'
AUTH=OUT/'SERVICE_RESTORATION.json'
STOP=ROOT/'runs/qamc_bace_v2/api/STOP'


def filehash(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    inputs=prepare_smoke()
    # Freeze the complete local source tree: no experiment silently executes a
    # changed shared transport/scorer. Pre-existing changes remain untouched.
    files=list((ROOT/'src/qamc').rglob('*.py'))
    files+=list((ROOT/'prompts/qamc_pa_v1').glob('*.md'))+list((ROOT/'prompts/preference_policy').glob('*.md'))
    files+=list((ROOT/'vendor/PrefEval/utils').glob('*.py'))+list((ROOT/'vendor/PrefEval/error_type').glob('*.txt'))
    files+=list((ROOT/'vendor/PrefEval/generation_task').glob('*.py'))
    files+=[ROOT/'literature/qamc_pa_v1/RPEval/prompts/prompts_715.py']
    # Source data and frozen inputs are included independently of executable code.
    for item in inputs['cases']:
        files.extend(ROOT/item[k] for k in ('public_path','evaluation_path','source_file'))
    plan={**inputs,'status':'FROZEN_PENDING_SERVICE_AND_OFFLINE_ACCEPTANCE',
          'request_cap':inputs['nominal_total_requests']+32,'reserve_requests':32,
          'reserve_scope':'only existing bounded precontent-429 recovery; no semantic retries',
          'concurrency':8,'case_workers':8,'spacing_seconds':3.1,'input_estimate_token_cap':32768,
          'maximum_output_tokens_per_physical_request':8192,
          'estimated_tokenizer':'cl100k_base heuristic, not provider tokenizer certification',
          'maximum_estimated_input_tokens':(inputs['nominal_total_requests']+32)*32768,
          'maximum_output_token_limits_sum':(inputs['nominal_total_requests']+32)*8192,
          'repair_requests_per_contract':0,'fallback':'cached matched G0 only, independently disclosed',
          'old_cumulative_cap_applies':False,'model':'qwen3.8-flash','temperature':0,
          'frozen_files':{str(p.relative_to(ROOT)):filehash(p) for p in sorted(set(files))},
          'legacy_stop_sha256':filehash(STOP),'automatic_development_dispatch':False,
          'service_confirmation_not_implied_by_plan':True}
    write_once(PLAN,plan);return plan


def preflight(require_service=False):
    plan=json.loads(PLAN.read_text())
    for name,h in plan['frozen_files'].items():
        if filehash(ROOT/name)!=h:raise ValueError('Frozen dependency changed: '+name)
    for item in plan['cases']:
        load_task(ROOT,item)
        if sha((ROOT/item['source_file']).read_bytes())!=item['source_sha256']:raise ValueError('Source changed')
    if require_service:
        if not AUTH.exists():raise ValueError('Awaiting direct user service-restoration confirmation')
        validate_service_authorization(json.loads(AUTH.read_text()),STOP)
    return plan


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['plan','preflight','run','report'])
    args=parser.parse_args()
    if args.command=='plan':
        plan=freeze();print(json.dumps({'roots':len(plan['cases']),'nominal':plan['nominal_total_requests'],'cap':plan['request_cap'],'new_model_calls':0}));return
    if args.command=='report':
        result=build_report(STAGE_RUN,OUT/'smoke',json.loads(PLAN.read_text()))
        print(json.dumps({'saved':result['saved_cells'],'ledger':result['ledger']}));return
    plan=preflight(require_service=args.command=='run')
    if args.command=='preflight':print(json.dumps({'offline_preflight':'PASS','service_confirmation_present':AUTH.exists(),'new_model_calls':0}));return
    with runner_lock(RUN/'runner.lock'):
        auth=json.loads(AUTH.read_text())
        g=StageGateway(STAGE_RUN/'api',plan,auth,STOP)
        exp=Experiment(g,ROOT,STAGE_RUN)
        try:
            with ThreadPoolExecutor(max_workers=plan['case_workers']) as pool:
                futures=[pool.submit(exp.case,item) for item in plan['cases']]
                for future in as_completed(futures):future.result()
        finally:
            g.export();build_report(STAGE_RUN,OUT/'smoke',plan)

if __name__=='__main__':main()
