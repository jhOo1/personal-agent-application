"""Persist-only paired vectors, separating author generator and same-Actor controls."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]
import qamc_contextual_match_persist_authors as run
from qamc_contextual_match_external_analyze import saved_waves
from qamc.common import sha
from qamc.contextual_match.evaluation import summarize,paired
from qamc.transport_helpers import atomic_json


def main(draws=2000):
    plan=run.read(run.OUT/'PLAN.json');run.check(plan,service=False)
    parent=run.read(run.parent.OUT/'PLAN.json')
    if (sha(parent)!=plan['parent_plan_sha256']
            or [c for c in parent['cases'] if c['benchmark']=='persistbench']!=plan['cases']
            or parent['service_reference_sha256']!=plan['service_reference_sha256']):
        raise ValueError('Persist comparison sources/service differ')
    for key in ('qwen','gpt41'):
        if parent['protocols'][key]['model']!=plan['protocols'][key]['model']:
            raise ValueError('Persist comparison models differ')
    for key,stage in (('qwen','Actor'),('gpt41','PersistJudge')):
        if parent['protocols'][key]['stages'][stage]!=plan['protocols'][key]['stages'][stage]:
            raise ValueError('Persist comparison decoding differs')
    pw,aw=saved_waves(run.parent.OUT),saved_waves(run.OUT)
    rows=[r for waves in (pw,aw) for _,w in sorted(waves.items()) for r in w['rows'] if r['benchmark']=='persistbench']
    common_actor=run.read(run.parent.audit.OUT/'PROMPTS.json')['base']['actor']
    for row in rows:
        if row['method']=='PB_FILTER_COMMON' and 'actor_request' in row:
            if (row['actor_request']['messages'][0]['content']!=common_actor
                    or sha(row['actor_request'])!=row['actor_request_sha256']):
                raise ValueError('Claimed common Actor changed')
    methods=list(parent['methods'])+plan['methods']
    table=[v for v in summarize(rows,plan['cases'],methods) if v['benchmark']=='persistbench']
    pairs=[{**paired(rows,plan['cases'],candidate,baseline,'persistbench',draws),
        'comparison_kind':'SHARED_ACTOR_SELECTION' if baseline=='PB_FILTER_COMMON' else 'FULL_SYSTEM_PROMPT_ADAPTATION'}
        for candidate in ('R0','R1','R2','R3','INCREMENTAL_UNIFIED_ADAPT') for baseline in plan['methods']]
    result={'parent_completed_waves':len(pw),'author_controls_completed_waves':len(aw),
        'selected_cases':60,'table':table,'paired':pairs,'native_protocol_parity_proven':False,
        'official_sota_proven':False,'new_model_calls':0,'human_review_count':0,'goal_complete':False}
    run.frozen(run.OUT/'analysis_snapshots'/(sha(result)+'.json'),result)
    atomic_json(run.OUT/'ANALYSIS_CURRENT.json',result)
    lines=['# PersistBench 作者对照：开发适配观察','',
        f'父实验 {len(pw)}/13 波，作者对照 {len(aw)}/13 波；未派发/失败为 NA，不填语义零。',
        '三类 FR@1 分别报告；这不是原生 Kimi/provider、CD/SY 三次采样的正式排名。','',
        '|方法|有效评分/60|CD FR@1|SY FR@1|BU FR@1|比较类型|','|---|---:|---:|---:|---:|---|']
    for row in table:
        values=[row['metrics'][k+'_FR_at_1'] for k in ('cross_domain','sycophancy','beneficial_memory_usage')]
        cells=['NA' if v is None else f'{v:.4f}' for v in values]
        track='作者生成提示＋同模型适配' if row['method'] in plan['table_tracks']['author_generator_adapted_model'] else '共同Actor系统提示'
        lines.append('|'+row['method']+'|'+str(row['valid_score_roots'])+'/60|'+'|'.join(cells)+'|'+track+'|')
    lines+=['','共同有效 UID、来源组 bootstrap 和全选题缺失界见 ANALYSIS_CURRENT.json。',
        'PB_FILTER 使用 Qwen 统一 backbone，区别于论文 v2 检索器 GPT-OSS-20B。GEPA 使用发布的优化提示，不重做其搜索。',
        '语义检索 8B 与论文阈值另行准备，不能用已缓存 0.6B 冒充；不能因此跳过其余可运行对照。']
    (run.OUT/'RESULTS_CURRENT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('table','paired')}))


if __name__=='__main__':main()
