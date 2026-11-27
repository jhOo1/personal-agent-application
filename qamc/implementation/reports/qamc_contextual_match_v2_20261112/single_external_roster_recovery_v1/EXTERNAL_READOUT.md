# Frozen single-preference selector on additional development groups

20 development groups had both exact historical RP and Des2Gen answers. All 20 entered the request plan. 16 produced complete third candidates, and 15 had strict scores for every candidate. The four missing MemAdapter candidates followed two URL errors and two timeouts during task-conditioned reflection. The two selectors use RP as fallback for those tasks. All 32 selector and 56 grading calls returned; two candidate scores failed the strict scoring contract. These results use the project detailed Qwen adaptation, with no human adjudication or independent confirmation.

| Common 15 sources | Match | OPB severity | UPB severity | FM severity |
|---|---:|---:|---:|---:|
| RP reconstruction | 13 | 0 | 1 | 6 |
| Des2Gen adaptation | 13 | 3 | 0 | 8 |
| MemAdapter FULL | 13 | 2 | 3 | 9 |
| Default-aware selection | 13 | 4 | 0 | 10 |
| V1 witnessed replacement | 14 | 1 | 1 | 7 |

V1 was one win, zero losses and fourteen ties against each comparator on the common slice. The winning task depends on the comparator. Across all 20 assignments, counting identical fallback answers as paired ties, V1's net Match gain over RP is exactly one even with the missing grade. Against ordinary selection the possible gain is one to two; against MemAdapter it ranges from minus one to plus five, with four unavailable counterfactual answers. These bounds describe missing observations, not sampling uncertainty.

Four of sixteen V1 decisions changed the default. On the Costa Rica adventure task, RP offered heights as optional despite the user's aversion. The selected response centered ground and water activities. Both selectors improved Match from 0 to 1. On a different task about solitary activities after moving, V1 kept RP, while the ordinary selector chose Des2Gen. Both drafts suggested crafts; the respective Match labels were 1 and 0. That single scoring difference is not evidence the ordinary selector failed to retrieve the preference. On the family film task, V1 treated a calm family film as conflicting with the requester's taste for suspense and switched. Match stayed 1, but OPB increased from 0 to 1. The other two switches concerned rail travel and vegan foundation; both left Match unchanged.

Keep the frozen implementation as a limited candidate. It improved Match on this additional development panel, but there was no second successful switch over RP, and its OPB and FM exceeded RP. The finding supports preserving a good default and sometimes switching; it does not demonstrate robust superiority over the three external methods or readiness for a SOTA claim. Physical cost was 56 candidate-stage + 32 selector + 56 Judge requests, 140 successful returns, 4 unknown deliveries, 513,723 reported tokens and 4 unknown usages, no retries. Both selectors used one additional call per available candidate triple. Cold deployment requires all three candidate pipelines as well.
