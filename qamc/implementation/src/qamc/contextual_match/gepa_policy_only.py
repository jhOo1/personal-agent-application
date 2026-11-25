"""Deletion ablation prototype: keep the released memory policy, drop app wrapper.

No new instructions, selected sources, task fields or use notes are introduced.
This is a footprint/control hypothesis, not a new algorithm contribution or a
faithful reproduction of the full released prompt. Execution needs its own
frozen finite runner; this module never dispatches calls.
"""
from copy import copy

from . import gepa_selected

MARKER="You are an AI assistant with access to the user's stored memories."


def policy_template(bridge):
    full=bridge.blobs['GEPA'].decode()
    if full.count(MARKER)!=1:raise ValueError('Pinned policy boundary changed')
    suffix=full[full.index(MARKER):]
    if suffix.count('{memories}')!=1 or '{memories}' not in full:raise ValueError('Memory renderer slot changed')
    return suffix


def actor(task, selector_answer, prompts, bridge):
    suffix=policy_template(bridge)
    adapted=copy(bridge);adapted.blobs=dict(bridge.blobs);adapted.blobs['GEPA']=suffix.encode()
    built=gepa_selected.actor(task,selector_answer,prompts,adapted,'GEPA_SELECTED_BOUNDS')
    built['audit'].update(complete_released_policy=False,complete_memory_policy_suffix=True,
        no_new_policy_words=True,original_template_characters=len(bridge.blobs['GEPA'].decode()),
        shortened_template_characters=len(suffix),is_deletion_ablation_not_native_reproduction=True)
    return built
