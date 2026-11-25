"""Only unissued Persist-author grades; independent score refresh, no new answers."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import qamc_contextual_match_persist_authors as run
from qamc.common import sha
from qamc.bace.runtime import runner_lock
from qamc.contextual_match.score_refresh import verify_refresh
import qamc.contextual_match.score_refresh as refresh_module
from qamc_contextual_match_components_scores import pending_jobs,validate_expected
from qamc.transport_helpers import atomic_json
from proposals.qamc_protocol_alignment.sampling import sampling_key


def main(action):
    plan=run.read(run.OUT/'PLAN.json');bridge=run.PersistAuthorBridge(run.parent.persist.UP)
    if bridge.manifest()!=plan['author_manifest']:raise ValueError('Pinned author assets changed')
    def lock_tool():
        run.frozen(run.OUT/'SCORE_TOOL_LOCK.json',{str(p.relative_to(ROOT)):run.parent.audit.file_sha(p)
            for p in (Path(__file__),Path(refresh_module.__file__),
                ROOT/'scripts/qamc_contextual_match_components_scores.py')})
    def check(value):run.check(value);lock_tool()
    lock_tool();run.check(plan,service=action=='run')
    executor=run.PhaseDispatcher(ROOT,run.OUT,run.RUN,plan,check,run.parent.audit.OUT.name)
    runtimes=executor.runtimes
    def collect(capture):
        waves=[]
        for path in sorted((run.OUT/'waves').glob('*.json')):
            original=run.read(path)
            waves.append(verify_refresh(original,run.collect_wave(plan,original['wave'],runtimes,capture,bridge)))
        return waves
    def export():
        waves=collect(lambda *_:None)
        result={'waves':waves,'completed_generation_waves':len(waves),'expected_waves':len(plan['waves']),
            'pending_unissued_grades':len(pending_jobs(run.OUT,plan,runtimes['gpt41'])),
            'parent_logical_guard':plan['logical_guard'],'budget_reset':False,'generations_unchanged':True,
            'previous_valid_scores_unchanged':True,'new_answers':0,'report_model_calls':0 if action=='report' else None,
            'goal_complete':False}
        run.frozen(run.OUT/'score_refreshes'/(sha(result)+'.json'),result)
        atomic_json(run.OUT/'CURRENT_SCORED_RESULTS.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='waves'}))
    if action=='run':
        run.ext.assert_parent_terminal()
        with runner_lock(run.parent.RUN/'runner.lock'),runner_lock(run.RUN/'runner.lock'):
            check(plan);expected={}
            def capture(name,jobs):
                if name.endswith('_judges'):
                    for j in jobs:expected[sampling_key(j['unit'])]=j
            collect(capture);jobs=pending_jobs(run.OUT,plan,runtimes['gpt41']);validate_expected(jobs,expected)
            executor.dispatch('late_scores_'+sha([sampling_key(j['unit']) for j in jobs])[:20],jobs)
            export()
    else:
        with runner_lock(run.RUN/'runner.lock'):export()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('run','report'))
    main(parser.parse_args().action)
