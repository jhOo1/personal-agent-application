"""Policy routing never receives dataset identity or evaluation labels."""
from .state_brief import FEATURES

def route(cards, features):
    features = set(features)
    if not features <= FEATURES: raise ValueError('unknown feature')
    matched = []
    for card in cards:
        if card.get('status') != 'VALIDATED': continue
        t = card['trigger']; a = set(t.get('all_of', [])); b = set(t.get('any_of', [])); n = set(t.get('none_of', []))
        if not (a|b|n) <= FEATURES: raise ValueError('unknown trigger')
        if a <= features and (not b or b & features) and not (n & features): matched.append(card)
    return [c['instruction'] for c in matched[:2]]

def assert_training_allowed(split):
    if split not in ('D_regression','D_opt','D_select'): raise ValueError('sealed split is not available to optimizer')
