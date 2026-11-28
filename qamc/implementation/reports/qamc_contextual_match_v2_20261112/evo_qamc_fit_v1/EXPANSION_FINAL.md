# QAMC source-separated expansion

All 162 exposed development tasks across three batches settled. The cohort excludes the 40-task fit panel and its source groups. It includes 126 RPEval tasks in 28 conservative source groups, 32 PersistBench tasks in 32 groups, and four BenchPreS tasks in one profile. Direct uses the released Self-ReCheck selector and the common evidence-only Actor. Parent and Scope both use the same selected original evidence and task-only plan. Their only request difference is the frozen Scope instruction. The transport audit verifies that difference for 55, 53 and 52 matched request pairs in the three batches. Project GPT-4.1, Qwen and GPT-4.1 scoring adaptations were fixed. These comparisons do not certify a published-protocol ranking or independent test.

| Common score | Archived specialist | Direct | Parent | Scope |
|---|---:|---:|---:|---:|
| RPEval Match, 121/126 tasks | 387/624 | 267/624 | 285/624 | 297/624 |
| RPEval OPB / UPB / FM | 128 / 108 / 23 | 308 / 38 / 72 | 209 / 110 / 66 | 175 / 121 / 65 |
| BenchPreS AAR, all four tasks, attribute-only replay | 4/4 | 2/4 | 2/4 | 1/4 |
| BenchPreS MR, same four tasks | 0/16 | 0/16 | 1/16 | 0/16 |
| BenchPreS completeness, two complete all-arm rows | 10/10 | 9/10 | 9/10 | 10/10 |
| PersistBench cross-domain pass | 12/12 | 6/12 | 10/12 | 12/12 |
| PersistBench sycophancy pass | 4/5 | 1/5 | 3/5 | 5/5 |
| PersistBench strict beneficial use | 13/13 | 13/13 | 13/13 | 13/13 |

The archived specialists are IPE-C, Strong Gate and PB_RUBRIC. Scope's equal-domain common macro leads its paired parent by 6.01 percentage points and Direct by 11.88 points, and trails the specialists by 10.11 points. The Scope–parent interval across the assigned cohort under extreme missing-grade completions is −2.44 to +11.81 points. The PersistBench improvement over PB_RUBRIC is one sycophancy case, the software project template, and the rubric did not detect all remaining historical influence in the other passes. [First-batch answer-level evidence](EXPANSION_FIRST_BATCH.md)

The archived SELECTED_GEPA is stronger than PB_RUBRIC in earlier development. A supplemental zero-call comparison on these 32 assigned PersistBench tasks verifies 30 exact common scoring envelopes and the saved answer–score bindings. Scope versus SELECTED_GEPA is 30/30 versus 29/30: CD 12/12 versus 11/12, SYC both 5/5 and strict BU both 13/13. The net one is a different track from the PB_RUBRIC difference. This matches grading protocol and evidence cohort, while generation pipelines and sampling runs differ. Use `bash run.sh expansion-persist-peer` to reproduce the comparison. [Earlier SELECTED_GEPA controls](../persist_selected_gepa_completion_v1/READOUT.md)

RPEval gives a narrow raw gain over the parent, with nine source-group wins, seven losses and 12 ties. Its advantage stays positive when leaving out each source group, +1.17 to +2.71 points, but excluding both methods' known judge flags changes Match to 220/445 versus 221/445 on 82 common tasks. Scope still lowers OPB (135 versus 145) with higher UPB (56 versus 53) in that subset. On tasks containing a C preference, the four-arm common Match is 176/307 versus 180/307, with UPB 59 versus 41. The 307 positions include A and B. Judge-compatible bounds for actual C Match difference include both directions, from −57 to +55 on 71 C positions. Inspected answers confirm real cases of weakened C, but also disagreement in reported ordinals and degree. [Paired answer audit](EXPANSION_TWO_BATCHES.md)

## The next mechanism to distinguish

The final route split confirms that 85 of the 90 positions separating Scope and IPE-C come from the 61 tasks on which IPE-C suppressed history, where Match is 113/275 versus 198/275. The current selector exposes history in 53/61 of those tasks. When IPE-C enables history, Scope is 184/349 versus IPE-C 189/349. These comparisons confound history exposure with the different generation pipelines. A matched change of actual exposure on a fixed Actor and task plan can isolate whether policy causes the loss.

The old IPE condition alone is insufficient. On six all-A tasks where it enables history, all four compared methods get 0/26, while the archived task-only endpoint is 26/26. On eleven B-only tasks where it disables history, Direct obtains 42/68 versus IPE-C 36/68 and Scope 33/68. These are diagnostics on archived grades, not online routing rules. The next test should compare a task-level activation policy with same-backbone always-off, selective exposure and ordinary full-history controls. It should protect both executable hard constraints and applicable soft preferences in cases with a shared decision. BenchPreS contributes a separate check of formal realization, including the documented bold omission with evidence already visible.

Scope is retained as a tested component and comparator. The current full pipeline should not replace the three strongest comparable methods on the strength of these results. No change to benchmark roles or sealed-data boundary was made by this experiment.

## Cost and reproducibility

Total 1,268 physical requests, including 106 planning, 141 selection, 481 Actor, and 540 grading requests. There were 1,266 transport successes and two unknown deliveries with no usage returned. Total reported tokens were 4,997,951. Missing contracts and transport failures remain in the outcome accounting. Reproduce the aggregate without model calls with `bash run.sh expansion-summary` in the experiment directory. [Aggregate JSON](EXPANSION_FINAL.json) · [Frozen protocol](EXPANSION_PROTOCOL.md)
