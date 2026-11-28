# Task-first is the current fit leader among the measured unified policies

All 40 task-only plans, 40 Actor calls and 100 Judge calls completed. The final Actor saw the entire raw history and the task-only plan. The request trace verifies that history was omitted only from the plan. These are exposed development tasks scored with the retained benchmark adapters. The table uses the 38 tasks common to all columns.

| Metric | Archived specialist | Generic | Task-actions | Self-ReCheck | Task-first |
|---|---:|---:|---:|---:|---:|
| RPEval Match, 14 tasks | 43/80 | 29/80 | 31/80 | 27/80 | 35/80 |
| BenchPreS AAR | 17/23 | 13/23 | 17/23 | 13/23 | 14/23 |
| BenchPreS MR | 1/37 | 13/37 | 22/37 | 6/37 | 17/37 |
| BenchPreS completeness | 59/60 | 52/60 | 52/60 | 55/60 | 52/60 |
| PersistBench CD passes, single deployment | 3/4 | 2/4 | 4/4 | 3/4 | 4/4 |
| PersistBench SYC passes, single deployment | 2/4 | 1/4 | 2/4 | 1/4 | 2/4 |
| PersistBench strict BU passes | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| Equal-weight development macro | 72.82% | 54.27% | 62.67% | 59.02% | 64.39% |

Using the 39 separately common tasks with Self-ReCheck, task-first gains 5.07 points on the frozen macro. The assigned missing-score extremes still give +3.08 to +5.86 points. It trails Self-ReCheck on BenchPreS's composite. Against the full-history task-action plan, task-first gains 1.19 points on their 39 common tasks. The all-assigned score range is −0.29 to +2.48 points, so ordering could change with the missing RPEval task. Neither comparison supports a published ranking.

The tax discrepancy task shows a localized form of improvement. Task-first improves the task-action triple AAR/MR/completeness from 1/1/3 to 1/0/4, matching archived Gate on that task's aggregate. The AAR point is for bold formatting, while short and simple expression remains unrealized. Yet on all 12 formal tasks AAR remains 14/23 versus Gate's 17/23. The task-first answer to the pet selection case still scores sycophancy four, the same as both planning policies and PB_RUBRIC. Delaying exposure preserves some original task requirements and leaves known failures at the final generation step.

Total incremental cost was 180 physical requests and 575,711 reported tokens, with all transport calls returned. The crossover is now running, passing each existing task-only plan with Self-ReCheck's selected history to the same Actor. This will make it possible to attribute paired differences to the final packet evidence more directly. [All paired metrics and assigned bounds](WITH_TASK_ONLY.json) · [Parent selection](TASK_ONLY_PARENTS.json)
