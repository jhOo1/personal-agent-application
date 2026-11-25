"""Separate baseline contract clarification; no change to ABC semantics or sources.

The first appendix adaptation collapsed eight MLE outputs into a global ranking.
This separate configuration requests the per-persona output required by the
paper's algorithm. It does not repair or replace any saved first-version output.
"""
from qamc.contextual_match import rpr_appendix as original

METHOD = 'RPR_APPENDIX_PER_PERSONA_V2'
generator_request = original.generator_request
rankings = original.rankings


def estimator_requests(task):
    requests = original.estimator_requests(task)
    count = len(task.memories)
    requests['MLE']['messages'][1]['content'] += (
        '\nPer-persona output contract: the ranking field must contain exactly '
        +str(count)+' ABC permutations separated by "|", one complete ranking '
        'for each listed persona entry in its original order. Do not merge the '
        'entries into one global ranking. Keep the same A/B/C definitions above.\n')
    return requests
