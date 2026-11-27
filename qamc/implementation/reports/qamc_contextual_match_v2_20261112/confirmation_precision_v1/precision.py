"""Best-case precision for a one-sided, zero-discordant-loss safety screen."""
import json
import math


def upper(n, alpha=0.05):
    return -math.expm1(math.log(alpha) / n)


def minimum_size(tolerance, alpha=0.05):
    n = math.ceil(math.log(alpha) / math.log1p(-tolerance))
    assert upper(n, alpha) <= tolerance < upper(n - 1, alpha)
    return n


print(json.dumps({
    "confidence": 0.95,
    "zero_losses_upper_bound": {n: upper(n) for n in (2, 12, 29, 59)},
    "illustrative_minimum_independent_roots_for_zero_losses": {
        p: minimum_size(p) for p in (0.05, 0.10, 0.20)
    },
}, indent=2))
