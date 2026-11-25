"""Offline candidate4 prototype: restore the frozen Actor's task contract.

Concatenates two existing complete instruction blocks, without new fields,
new selection or new evidence. This is not a native GEPA reproduction. No
request is sent here; an independent finite execution freeze is required.
"""
from copy import copy
from .gepa_policy_only import policy_template
from . import gepa_selected


def actor(task, selector_answer, prompts, bridge):
    template=prompts['actor'].rstrip()+'\n\n'+policy_template(bridge)
    adapted=copy(bridge);adapted.blobs=dict(bridge.blobs);adapted.blobs['GEPA']=template.encode()
    built=gepa_selected.actor(task,selector_answer,prompts,adapted,'GEPA_SELECTED_BOUNDS')
    built['audit'].update(complete_released_policy=False,restored_original_task_contract=True,
        complete_memory_policy_suffix=True,no_new_instruction_wording=True,
        is_two_existing_instruction_blocks_not_new_optimizer=True)
    return built
