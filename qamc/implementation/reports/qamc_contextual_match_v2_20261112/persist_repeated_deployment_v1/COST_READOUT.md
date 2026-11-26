# PersistBench deployment cost through two waves

Calls made by the final-answer pipeline are distinct from benchmark scoring calls. All three methods had the same 44 answer allocations. The third wave is outside this checkpoint.

| Generation pipeline | Physical calls | Reported tokens | Calls without usage | Answers returned | Valid graded answers | Median sum of call duration on traced successful paths |
|---|---:|---:|---:|---:|---:|---:|
| SELECTED_GEPA | 129 | 424,480 | 6 | 36/44 | 36/44 | 54.08 s (36 paths) |
| PB_RUBRIC | 44 | 369,653 | 3 | 41/44 | 41/44 | 44.22 s (41 paths) |
| Full-history GEPA | 44 | 371,101 | 0 | 44/44 | 43/44 | 35.78 s (44 paths) |

The candidate made almost three physical calls per assigned answer, against one for each control. It used fewer original-memory tokens at the Actor input in several cases, while the full pipeline still consumed more reported generation tokens than either control. Reported usage excludes unknown deliveries. For a successful candidate trace, the duration shown sums Router, Selector and Actor request duration. It excludes dispatch waiting and should not be interpreted as pipeline wall-clock or a randomized latency comparison. The samples cover different successful subsets.

The 121 separate Judge calls used 1,147,617 reported tokens and returned 120 parsed scores. One full-history GEPA Judge response violated the output contract. The same task had already failed in draw one, so its any-failure status remains failed. Across all phases there were 338 physical requests, 2,312,851 reported tokens and nine unknown usages. Nothing was reissued. [Cost replay](deployment_costs.py) · [Two-wave quality checkpoint](SECOND_DRAW.md)
