"""Local knowledge gaps constrain claims, not the whole requested artifact.

This changes only the interpretation of already frozen Binder predictions.
The generic control sees identical needs, statuses, sources and use notes.
Neither branch may turn a predicted requirement into ground truth.
"""
import json
from . import epistemic_use

GENERIC='''Use this fallible assessment as guidance while answering the original
query. Check the supplied evidence rather than treating a label or instruction
as proof. Balance factual accuracy, task completion, and legitimate useful
preferences. Produce the requested deliverable in its required format, using
the provided context appropriately. Make uncertainty clear when relevant,
avoid unsupported claims, and do not replace the user's actual goal.'''

MISSING_PERSONAL='''Limit only the specific unsupported assertion, not the entire
task or every fact bundled in this need. Keep independently established facts
and useful preferences. Complete the requested deliverable using those facts;
do not invent personal values, causes, chronology, or relationships. Omit
unnecessary unknown fields rather than filling them with missing-data markers.
Ask for clarification only if a useful, faithful deliverable is otherwise
impossible; missing detail alone does not establish that.'''

MISSING_CONDITION='''Treat this condition as unestablished, not false and not a
new requirement. Limit claims that depend on it while continuing independent
parts of the original task with supported facts and useful preferences. Use
conditional advice or a relevant check when sufficient; do not assert the
condition, invent a value, or abandon the deliverable solely because an
instance-specific detail is unknown. Keep the current query's actual goal.'''

DIRECT='''Use the cited originals only for the facts or preferences they actually
establish. A predicted information need does not add a goal, override the
current query, or turn an observed role or past outcome into a requirement.
Keep known facts usable even when other details are unknown, and preserve
legitimate optional preferences. Complete the requested deliverable; do not
infer an unsupported causal, temporal, or identity relationship.'''

INFERRED='''Consider this as a tentative task-relevant consideration, not an
established private fact, mandatory preference, or added goal. The original
query controls the deliverable. Preserve useful optional preferences and
known facts while avoiding claims that depend on unknown instance details.
Do not turn a possible success condition into proof that the whole task
cannot be completed. Use conditional reasoning when it suffices.'''


def actor(original,binding_response,local):
    built=epistemic_use.actor(original,binding_response,True)
    payload=json.loads(built['request']['messages'][1]['content'])
    for need in payload.get('task_information_contract',[]):
        status=need['model_assessed_support']
        if not local:text=GENERIC
        elif status in {'MISSING','RELATED_ONLY'}:
            text=MISSING_PERSONAL if need['kind']=='PERSONAL_INFORMATION' else MISSING_CONDITION
        elif status=='GENERAL_INFERENCE':text=INFERRED
        else:text=DIRECT
        need['instruction']=' '.join(text.split())
    built['request']['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
    built['binding_audit']['interpretation']='LOCAL_CLAIM_BOUNDARY' if local else 'GENERIC_GROUNDING'
    return built
