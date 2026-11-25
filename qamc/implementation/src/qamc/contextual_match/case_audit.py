"""Evaluation-only audit facts; no semantic verdicts or inference dependencies.

Author-label disagreements and unusual judge counts are review flags, never
automatic corrections. Source omission does not prove absence from an answer.
"""
from copy import deepcopy
from qamc.common import sha

VERSION='source_case_audit_v1'
SINGLE_LABELS={'ignore':'A','忽略偏好':'A','support':'B','supportive':'B','支持性偏好':'B',
    '尝试支持性':'B','dominate':'C','dominant':'C','以偏好为主线':'C'}


def observed_failure(row):
    read=row.get('read_status','UNKNOWN');actor=row.get('actor_status','UNKNOWN')
    if read=='MISSING_REPRESENTATION':return 'REPRESENTATION_UNAVAILABLE'
    if read=='INVALID':return 'SELECTOR_CONTRACT'
    if read not in ('OK','VALID','NOT_REQUIRED'):
        return 'SELECTOR_UNAVAILABLE_OR_UNISSUED'
    if actor!='OK':return 'ACTOR_'+actor
    if row.get('score') is None:
        return 'JUDGE_CONTRACT' if row.get('score_error_type') else 'JUDGE_UNAVAILABLE_OR_UNISSUED'
    return 'UNKNOWN_SEMANTIC_FIRST_ERROR'


def author_applicability(task,row,reference):
    # A/B/C influence strength is not text-level PARTIAL. This diagnostic only
    # compares presence/absence, without treating B/C as distinct Actor inputs.
    strategy=reference.get('intent_type')
    if len(task.memories)==1 and not isinstance(reference.get('persona'),list):
        strategy=SINGLE_LABELS.get(strategy,strategy)
    if (not isinstance(strategy,str) or len(strategy)!=len(task.memories)
            or set(strategy)-set('ABC')):
        return {'status':'UNKNOWN_AUTHOR_ALIGNMENT','positions':[]}
    view=row.get('view',{})
    if 'source_evidence' not in view:
        return {'status':'NO_ORIGINAL_SOURCE_SELECTION_VIEW','positions':[]}
    selected={v['memory_id'] for v in view['source_evidence']}
    positions=[]
    for memory,label in zip(task.memories,strategy,strict=True):
        keep=memory.memory_id in selected
        flag='A_ADMITTED' if label=='A' and keep else 'BC_DROPPED' if label!='A' and not keep else None
        positions.append({'memory_id':memory.memory_id,'author_label':label,'retained_in_actor_input':keep,
            'author_label_disagreement':flag,'semantic_error_proven':False})
    score=row.get('score') or {}
    review_flag=(set(strategy)=={'A'} and score.get('matched')==0
        and score.get('total')==len(strategy) and len(selected)<len(strategy))
    rubric_flags=[]
    if set(strategy)=={'A'} and score.get('severity',{}).get('UPB',0)>0:
        # Archived UPB is C/B -> A. An all-A target cannot establish that
        # transition. This flags a definition dispute, never overwrites UPB.
        rubric_flags.append('ALL_A_TARGET_WITH_NONZERO_UPB_REQUIRES_RUBRIC_REVIEW')
    return {'status':'AUTHOR_LABEL_DIAGNOSTIC_NOT_ADJUDICATION','positions':positions,
        'all_ignore_zero_match_with_some_sources_excluded_needs_answer_review':review_flag,
        'rubric_definition_review_flags':rubric_flags,
        'excluded_source_implies_answer_did_not_use_it':False,'automatic_score_correction':False}


def actor_input_groups(rows):
    groups={}
    for row in rows:
        key=row.get('actor_request_sha256')
        if key:groups.setdefault(key,[]).append(row)
    return [{'actor_request_sha256':key,'methods':[r['method'] for r in values],
        'distinct_saved_answers':len({sha(r['answer']) for r in values if 'answer' in r}),
        'distinct_valid_scores':len({sha(r['score']) for r in values if r.get('score') is not None}),
        'same_wire_does_not_prove_deterministic_answers_or_judges':True}
        for key,values in sorted(groups.items()) if len(values)>1]


def blind_packet(task,rows):
    # Salted stable order avoids identifying a method by its pipeline order.
    ordered=sorted(rows,key=lambda r:sha(['qamc_blind_source_audit_v1',task.uid,r['method']]))
    public={'review_id':sha(['qamc_case',task.uid])[:20],'query':task.query,
        'current_context':task.current_context,'fixed_facts':list(task.fixed_facts),
        'original_memories':task.payload()['memories'],'variants':[],
        'human_review_count':0,'completed_review':False,
        'review_questions':['Which original preferences apply to the unchanged request and actual beneficiary?',
            'Which retained/excluded sources cause a supported overuse or underuse?',
            'Does the answer use evidence correctly, including qualifications and negation?',
            'Is any alleged error only a judge or author-label disagreement?']}
    key=[]
    for index,row in enumerate(ordered):
        alias=f'V{index+1}'
        public['variants'].append({'variant_id':alias,'compiled_actor_evidence':deepcopy(row.get('view')),
            'final_answer':row.get('answer'),'generation_availability':row.get('actor_status','UNKNOWN')})
        key.append({'variant_id':alias,'method':row['method']})
    return public,key
