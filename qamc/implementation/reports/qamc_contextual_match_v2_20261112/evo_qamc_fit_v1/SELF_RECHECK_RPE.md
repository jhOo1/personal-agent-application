# Direct selection reduced exposure and increased judged misuse on RPEval

The released Self-ReCheck selector had 16 assigned RPEval tasks. All reached the Actor. All 16 scoring requests returned, 15 with usable project-adapter grades. Four methods share 14 valid tasks and 80 evaluated positions.

| Same 14 tasks | IPE-C | Full-history generic plan | Full-history action plan | Self-ReCheck |
|---|---:|---:|---:|---:|
| Match | 43/80 | 29/80 | 31/80 | 27/80 |
| OPB severity | 13 | 30 | 32 | 43 |
| UPB severity | 18 | 14 | 13 | 4 |
| FM severity | 3 | 9 | 7 | 9 |
| All-A Match | 7/25 | 0/25 | 0/25 | 0/25 |
| All-A OPB severity | 5 | 12 | 12 | 19 |
| Match without known flags, seven tasks | 21/43 | 16/43 | 18/43 | 16/43 |

The selector exposed 41/96 original memories, retaining every B and C in the assigned panel. It reduced judged underuse relative to both planning arms but increased judged overuse. Matters of concentration and salience remain hypotheses. Self-ReCheck changes both the planning pipeline and final evidence, and no causal effect of removing sources alone can be estimated from this comparison. The pending fixed-plan crossover will hold the task-only plan and final instructions constant.

- In `explicit/141` (lunch with a manager and coworkers), only one memory was retained. The delivered answer explicitly uses the requester's customary lunch efficiency to screen venues for the group. This is a concrete survivor of filtering, rather than an inference from the grade.
- In `explicit/064` (museum with a child), two memories were retained. The final answer recommends interactive exhibitions and also foregrounds the requester's historical interest in nature and science. This is the same attribution seen in the full-history action answer. Distinguishing appropriate family activities from the reason for prioritizing them remains necessary.

The scoring stage replay made no calls. The 16 existing scoring requests reported 56,926 tokens. Continue to report the isolated RPEval finding alongside the other two benchmarks when those scores settle. [Stage scoring output](SELF_RECHECK_RPE.json) · [Exposure audit](SELF_RECHECK_EXPOSURE.md)
