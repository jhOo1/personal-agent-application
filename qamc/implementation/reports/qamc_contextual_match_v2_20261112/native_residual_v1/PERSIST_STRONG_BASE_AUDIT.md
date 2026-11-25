# PersistBench archived stronger-base comparison

The fixed-evidence factorial's SELECTED_GEPA path passed 11/12 in its original panel, against SELECTED_NATIVE 10/12 and FULL_GEPA 9/12. The candidate did not pass its frozen net-win requirement against SELECTED_NATIVE. This path combines archived grounding with the released author GEPA prompt.

Joining by task UID, nine factorial tasks overlap the current PB_RUBRIC census. SELECTED_GEPA passes 8/9 and PB_RUBRIC 6/9 on those tasks. The overlap shrinks to five tasks from the policy-search panel (4/5 versus 3/5) and three from the criteria pilot (2/3 versus 1/3). These are useful archived differences, with different evidence paths and no established exact scorer-request equivalence across the old factorial and newer archive. They do not establish superiority on the full census.

The full-memory author PB_GEPA control in the newer author-control waves has 48 common scored census tasks. Using strict utility for BU and release failure for CD/SYC, PB_RUBRIC passes 43/48 and PB_GEPA 39/48. PB_GEPA has zero wins and four losses against PB_RUBRIC. On the policy-search 12-root split both pass 9/12. On the group-out split one PB_GEPA result is missing; on the remaining 11 it passes 7/11 to PB_RUBRIC's 9/11. These are project-adapted results, not parity with the published Kimi evaluation.

No generations or scores were repeated. Preserve PB_RUBRIC as the broader verified reference. The only potentially stronger archived component is selected evidence with GEPA, which needs an exact matched score and evidence audit before attempting to expand it. Do not substitute FULL_GEPA as a proxy for that combination.

## Exact scoring-input comparison

All nine overlapping SELECTED_GEPA/PB_RUBRIC tasks have archived Judge manifests. On each, the system message and all request parameters are identical. Each user message contains its corresponding saved answer exactly once. Replacing only that answer with the same placeholder makes the two complete user messages identical on all nine tasks. Thus the 8/9 versus 6/9 comparison is compatible at the project scoring-input level. It still compares distinct Actor evidence and prompt paths and separate historical calls. No equivalence of underlying provider weights or author-native protocol is established.

## All six released controls

Recomputing paired results directly from all 13 saved author-control waves under CD/SYC release and BU strict utility yields the following. The PB_RUBRIC count changes with the common denominator.

| Control | Common | PB_RUBRIC pass | Control pass | Control wins / losses |
|---|---:|---:|---:|---:|
| PB_GEPA | 48 | 43 | 39 | 0 / 4 |
| PB_FULL | 48 | 42 | 39 | 0 / 3 |
| PB_FILTER_NATIVE | 46 | 40 | 35 | 0 / 5 |
| PB_FILTER_COMMON | 47 | 41 | 29 | 1 / 13 |
| PB_NO_MEMORY | 47 | 41 | 29 | 5 / 17 |

The two filtering controls do not reproduce the archived Grounding policy. Grounding first routes from the query, uses Style evidence on the history-check branch, and otherwise invokes the original Grounding selector. The 11/12 factorial reuses those already-frozen selections. A larger test must execute the same upstream policy or explicitly label a different selector. No equivalent SELECTED_GEPA run beyond the original factorial was found in the result archive search.
