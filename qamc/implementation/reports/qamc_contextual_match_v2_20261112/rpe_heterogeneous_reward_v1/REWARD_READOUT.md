# Archived reward-model comparison

The pinned InternLM2-7B reward run finished on all 24 exposed RPEval single-preference items. It scored the same three complete archived candidates per task. The model received the task and raw history as the user message and each candidate as the assistant message. Candidate IDs and method names were absent from that input. Selection of the greatest scalar score was frozen before joining grades. This is a historical local inference diagnostic. Subsequent experiments use the API-only protected-repair design.

| 22 historical common tasks | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| RP reconstruction | 17/22 | 0 | 7 | 17 |
| Des2Gen adaptation | 18/22 | 1 | 7 | 23 |
| MemAdapter adaptation | 18/22 | 3 | 3 | 14 |
| Qwen ordinary blind selection | 17/22 | 2 | 2 | 15 |
| InternLM2 reward selection | 19/22 | 1 | 2 | 14 |
| Qwen conflict-witness V1 | 19/22 | 1 | 2 | 12 |

The two latter methods chose different candidates on 13 of 22 common items, with identical Match outcome on every item. Reward selection switched away from RP in 15 of 24 cases, versus five for V1. On the 21 tasks where ordinary selection also delivered, both reached 18/21 alongside MemAdapter. On all 24 assigned items, both reached 21/24 with identical itemwise Match. Relative to RP, reward selection recovered the same two C misses and created no Match regressions. The remaining A, B and C misses were shared. Differences in FM and other rubric fields still matter. On the Japan task, reward selected RP and V1 selected Des2Gen. Both pass the frozen scorer, and the behavior and scoring caveats are discussed in the [default-aware control](../rpe_constraint_veto_v1/DEFAULT_CONTROL_READOUT.md).

Local execution finished 24 groups and 72 candidate scores with 77,102 reported input tokens and 4,745 total summed batch seconds on the recorded host. The separate historical Qwen blind comparison made 24 physical requests, including two unknown deliveries, with 97,447 reported tokens and no retries. The local reward run made no cloud requests and reused the grades already bound to the exact candidate answers. Zero new Actor or Judge requests were needed. The small, exposed test and common adapted grader support comparison of the two realized selection policies. They leave performance under the official protocol unresolved.

[Aggregates](REWARD_SUMMARY.json) · [Methods and freeze](PROTOCOL.md) · [Settlement and recovery](SETTLEMENT.md)
