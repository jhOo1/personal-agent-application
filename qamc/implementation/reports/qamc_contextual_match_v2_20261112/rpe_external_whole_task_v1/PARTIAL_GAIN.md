# Where does the position-level gain occur?

Fixed intersection of 211 exposed tasks and 1,124 positions. Bins use both answers' recorded exactness after scoring. A gain is the positive difference in matched-position counts for one task; a loss is the magnitude of a negative difference. These counts do not identify which individual memory changed or supply a deployable rule.

| Pair outcome | Tasks vs empty | Positions gained / lost | Tasks vs reconstructed RP | Positions gained / lost |
|---|---:|---:|---:|---:|
| Both exact | 78 | 0 / 0 | 49 | 0 / 0 |
| Only IPE-C exact | 1 | 4 / 0 | 30 | 130 / 0 |
| Only comparator exact | 9 | 0 / 37 | 4 | 0 / 13 |
| Neither exact | 123 | 95 / 2 | 128 | 4 / 13 |

Relative to empty history, 93 net points accrue on tasks both methods still miss. Losing 33 net points on exactness reversals leaves 60 net across all tasks. On 83 C-bearing tasks, 81 remain imperfect under both arms (+92, −2), while two exact empty-history rows cost four points. Both concern one family outing; their shared empty answer recommends a craft activity despite a no-crafts constraint. Consult the original [answer and scoring audit](../paper_rpe_paired_uncertainty_v1/EXACT_REVERSALS.md). Seven all-ignore rows move from exact under empty history to zero under IPE-C; the picnic task with a group-size restriction is among them.

Relative to reconstructed RP, 117 net points come from tasks where exactly one answer is exact. Both-imperfect tasks contribute minus nine. Hence a position-level improvement against both comparators has two different observed explanations. The empty comparison supports partial recovery of useful behavior according to the grader; the RP comparison principally supports avoiding harmful exposure. Neither comparison establishes reliable completion of mixed tasks. [Aggregate](PARTIAL_GAIN.json) · [Reproduction](partial_gain.py)
