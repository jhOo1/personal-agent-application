# Filtering reduced RPEval Match with the initial plan held fixed

All 16 RPEval tasks have both project-adapter scores. The same task-only plan, Actor system prompt and configuration were used for each pair. The evidence list changed from all original sources to Self-ReCheck's ordered subset.

| Same 16 tasks, 96 positions | Task-first, full history | Task-first, selected history |
|---|---:|---:|
| Match | 42/96 | 38/96 |
| OPB severity | 27 | 29 |
| UPB severity | 17 | 16 |
| FM severity | 9 | 9 |
| All-A Match, five tasks | 3/25 | 1/25 |

The all-A delta is concentrated in the manager-and-coworkers lunch case, which falls from 3/3 to 1/3 and OPB from 0 to 2. The selected packet preserves the personal lunch-efficiency source, and the final answer actively uses it to prioritize a restaurant option. In the parent answer, the same source was present among the full history but was not invoked as a personal justification. The parent paid attention to current location and the group lunch. On the museum task the score falls from 6/7 to 2/7. The concentrated exposure still leaves the requester's interest in nature and science visible in an answer for a child. These are actual single-deployment examples, so additional samples would be needed to estimate recurrence.

This result adds a stricter contrast to the uncontrolled Self-ReCheck vs planning comparison. Controlling the plan and final prompt still did not make reduced exposure sufficient to improve these RPEval outcomes. BenchPreS and PersistBench scores are being evaluated separately. The selected-exposure planning comparison will reuse the same chosen sources to test whether a different way of planning their use changes the three-domain trade-off. [Exact paired results and call counts](CROSSOVER_RPE.json) · [Verified request contract](CROSSOVER_CONTRACT.md)
