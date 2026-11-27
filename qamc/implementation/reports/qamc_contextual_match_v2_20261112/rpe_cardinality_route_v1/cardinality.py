"""Choose the original RPEval history request by candidate count."""


def use_history(original_count, ipe_uses_history):
    if type(original_count) is not int or original_count < 0 or type(ipe_uses_history) is not bool:
        raise ValueError("Expected the original candidate count and IPE history decision")
    if original_count == 0:
        return False
    return original_count == 1 or ipe_uses_history
