"""Complete the selector-by-Actor crossing with saved effect predictions.

There are no new rules, source judgements, repair calls or optimized prompts.
The public User, chosen original spans and bounded notes stay identical to C5;
only the Actor system switches to the already evaluated complete author policy.
"""
import json
from . import goal_effect,gepa_selected


def actor(task,raw,prompts,bridge):
    decoded=goal_effect.decode(task,raw)
    built=gepa_selected.actor(task,json.dumps(decoded['selection'],ensure_ascii=False),
        prompts,bridge,'GEPA_SELECTED_BOUNDS')
    built['effect_audit']={'rows':decoded['effects'],'semantic_effects_guaranteed':False,
        'effect_codes_hidden_from_actor':True,'source_order_preserved':True,'uncertainty_policy_changed':False}
    built['audit']['selector_actor_crossing_not_new_prompt_search']=True
    return built
