"""Offline, explicitly AI-adjudicated sensitivity layer; never overwrite native scores."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'reports/qamc_rpreasoner_contract/ALL_CASE_DETAILS.json'
OUT = ROOT / 'reports/qamc_rpreasoner_contract/score_review'


def main():
    before = SOURCE.read_bytes()
    cases = json.loads(before)
    case = next(c for c in cases if c['uid'].endswith('implicit_preference/single/16'))
    results = case['new_results'] + [x['result'] for x in case['old_controls']]
    assert len(results) == 7
    assert case['evaluation_only_reference']['intent_type'] == 'ignore'
    rows = []
    # This is a recorded source-level AI decision, not an automated semantic classifier.
    for result in results:
        answer = result['answer']
        assert answer and ('冒险' in answer or '刺激' in answer)
        rows.append({
            'arm': result['arm'], 'answer': answer,
            'answer_sha256': hashlib.sha256(answer.encode()).hexdigest(),
            'native_score': result['score'],
            'ai_adjudicated_match': {'matched': 0, 'total': 1},
            'adjudicated_severity': None,
            'basis': '统一采用本题原始ignore标签的严格解释：主动将刺激、悬念、反转作为选片或排序目标属于Support，家庭友好不等同于Ignore。并非只因影片含冒险元素就扣分。',
        })
    report = {
        'version': 'rpreasoner_dispute_ai_v1', 'reviewer': 'Codex AI',
        'human_review_count': 0, 'new_model_api_requests': 0,
        'review_type': 'unblinded_posthoc_semantic_sensitivity',
        'source_sha256': hashlib.sha256(before).hexdigest(),
        'native_scores_unchanged': True,
        'case': {k: case[k] for k in ('uid', 'original_public_input', 'evaluation_only_reference')},
        'rows': rows,
        'conclusion': 'RP_SHARED_ACTOR的本题1/1在此统一严格口径下改为0/1；其余六组仍0/1。撤销此题相对Gate的胜出，不代表其他题已复核，也不证明历史偏好的因果作用。',
        'limitations': [
            '语义裁决，不是确定的解析代码修复；宽松解释也可能合理，因此单独报告，不改原生主分。',
            '已知方法名称和旧分，非盲审、非独立测试、非人工真值。',
            '不能把本次复核成绩与论文原生指标混称协议可比SOTA。',
        ],
        'unresolved': [{
            'uid': 'rpeval/fused/explicit_preference/multi/138',
            'issue': 'G0/V0/F0的Judge称只有运动偏好未使用，却返回2/4，理由与计数冲突。RP_SHARED_ACTOR未收到运动来源，但回答出现身体想动的措辞；这既不能证明用了该历史，也不能单凭未检索证明答案符合ignore。',
            'action': '保留原分，不用Judge理由自动改成1/4；完整逐偏好、逐答案复核后才给该题统一修订分。',
        }],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'ADJUDICATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'README.md').write_text('''# RPReasoner 评分争议复核\n\n本轮为 Codex AI 离线复核，真人审核 0，新增模型 API 请求 0。完整来源、七组回答、原Judge及修订值见 ADJUDICATION.json。\n\n## 家庭电影题 implicit/single/16\n\n原标签是 ignore。七组答案都主动保留刺激、冒险或悬念作为推荐目标；共享Actor还明确写“整体偏冒险、喜剧、节奏快、有悬念或反转”。原Judge对旧基线的较弱表述判错，对共享Actor判对，尺度不一致。\n\n按统一严格解释，七组均为0/1，共享Actor由1/1修订为0/1。撤销该题的表面胜出。此为语义敏感性分析，不是无争议的程序错误；所有原生分数与严重度保留，修订严重度为NA。不以复核分覆盖主表，不据此宣称SOTA。\n\n## 乐器题 explicit/multi/138\n\nG0/V0/F0理由写“只有运动健身类未被利用”，却计2/4，确有内部冲突。但理由本身也可能错误，不能机械改分。共享Actor未收到运动来源也不足以证明最终答案完全忽略该偏好。暂记录争议，不补造确定分数。\n\n## 可复现边界\n\n脚本 audit_rpreasoner_disputed_scores.py 只封装已完成的AI裁决并核验输入完整性，不是新的语义评分器。全方法一致应用，完整答案留存；非盲审、非人工审核、非独立确认。该审阅不更改模型输入、Gold或旧账本。\n''')
    assert SOURCE.read_bytes() == before
    print(json.dumps({'reviewed_answers': len(rows), 'changed_scores': sum(r['native_score']['matched'] != 0 for r in rows), 'new_api_requests': 0}))


if __name__ == '__main__':
    main()
