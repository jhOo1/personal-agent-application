"""Deterministic maximum coverage and equal-size independent control."""
from itertools import combinations
import math

THRESHOLD = 0.07


def select(matrix):
    if not matrix or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("Expected a rectangular matrix with original-query row zero")
    if not all(math.isfinite(v) for row in matrix for v in row):
        raise ValueError("Non-finite MemGate score")
    original = matrix[0]
    base = [i for i, score in enumerate(original) if score > THRESHOLD]
    k = len(base)
    if k == 0:
        return base, [], []
    positive = [[max(0.0, x - THRESHOLD) for x in row] for row in matrix]
    maximal = [max(col) for col in zip(*positive, strict=True)]
    ranking = sorted(range(len(original)), key=lambda i: (-maximal[i], -original[i], i))

    def preference(indices):
        coverage = math.fsum(max(row[i] for i in indices) for row in positive)
        total_original = math.fsum(original[i] for i in indices)
        # Round only the two aggregate comparisons to remove representation-level ties.
        return round(coverage, 12), round(total_original, 12), tuple(-i for i in indices)

    cover = max(combinations(range(len(original)), k), key=preference)
    return base, sorted(ranking[:k]), list(cover)
