"""All 60 public cases through author controls with no model or scoring calls."""
from collections import Counter
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import qamc_contextual_match_persist_authors as run
from qamc.common import sha
from proposals.qamc_protocol_alignment.sampling import sampling_key,validate_public_request


def main():
    plan=run.read(run.OUT/'PLAN.json');run.check(plan,service=False)
    bridge=run.PersistAuthorBridge(run.parent.persist.UP)
    tasks={c['uid']:run.parent.smoke.task_for(c) for c in plan['cases']}
    stored={};checks=[];rows=[];allowed=set(plan['allowed_unit_keys'])
    before=sorted(str(p) for p in run.RUN.glob('*/outputs/*.json'))
    class RT:
        def output(self,unit):return stored.get(sampling_key(unit))
    rt={'qwen':RT(),'gpt41':RT()}
    def dispatch(name,jobs):
        if name.endswith('_judges'):raise AssertionError('Offline author preflight cannot grade')
        for j in jobs:
            key=sampling_key(j['unit']);stage=j['unit']['stage'];body=j['request']
            if key not in allowed:raise AssertionError('Job outside frozen author allocation')
            validate_public_request(body)
            protocol=plan['protocols'][run.model_block(stage)]
            if (j['unit']['protocol_sha256']!=sha(protocol) or body['model']!=protocol['model']
                    or body['temperature']!=0 or body['max_tokens']!=protocol['stages'][stage]['max_tokens']):
                raise AssertionError('Author fixture decoding differs')
            if key in stored:
                if stored[key]['request_sha256']!=sha(body):raise AssertionError('Author fixture wire changed')
                continue
            task=tasks[j['unit']['root_id']]
            answer=json.dumps({'useful_memories':[m.text for m in task.memories[:2]]}) if stage=='Selector' else 'FIXTURE_NOT_A_MODEL_ANSWER'
            stored[key]={'unit':j['unit'],'request_sha256':sha(body),'status':'OK','response':{'answer':answer}}
            checks.append({'unit':j['unit'],'request_sha256':sha(body)})
    # Persist references share a source JSONL with public fields. task_for has
    # already loaded the frozen public task files; generation must not reopen
    # the native evaluation row/rubrics when scoring is disabled here.
    with patch.object(run.ext,'grade_rows',lambda *_:None),\
        patch.object(run.parent.persist,'source',side_effect=AssertionError('No evaluation rows in fixture generation')),\
        patch.object(run.parent.persist,'upstream',side_effect=AssertionError('No evaluation rubrics in fixture generation')),\
        patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No offline HTTP')) as http:
        for wave in range(len(plan['waves'])):
            result=run.collect_wave(plan,wave,rt,dispatch,bridge)
            if result!=run.collect_wave(plan,wave,rt,lambda *_:None,bridge):raise AssertionError('Fixture replay changed')
            for row in result['rows']:
                if 'actor_request' not in row or row['score'] is not None:raise AssertionError('Fixture failed or produced a score')
                if row['method']=='PB_FILTER_COMMON' and row['actor_request']['messages'][0]['content']!=run.read(run.parent.audit.OUT/'PROMPTS.json')['base']['actor']:
                    raise AssertionError('Shared Actor changed')
                rows.append({'uid':row['uid'],'method':row['method'],'table_track':row['table_track'],
                    'actor_request_sha256':row['actor_request_sha256']})
        if http.call_count:raise AssertionError('Offline author preflight called HTTP')
    if before!=sorted(str(p) for p in run.RUN.glob('*/outputs/*.json')):raise AssertionError('Fixture changed real outputs')
    result={'frozen_public_cases':60,'fixture_method_cells':len(rows),'unique_non_judge_units':len(checks),
        'cells_by_method':dict(Counter(r['method'] for r in rows)),'real_model_calls':0,
        'benchmark_scores_generated':0,'evaluation_rows_or_rubrics_read_during_generation':0,
        'native_prompts_not_shortened':True,'real_output_files_unchanged':True,
        'fixture_is_not_semantic_acceptance':True,'native_protocol_parity_proven':False,
        'requests':checks,'actor_requests':rows}
    run.frozen(run.OUT/'OFFLINE_PIPELINE_ACCEPTANCE.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('requests','actor_requests')}))


if __name__=='__main__':main()
