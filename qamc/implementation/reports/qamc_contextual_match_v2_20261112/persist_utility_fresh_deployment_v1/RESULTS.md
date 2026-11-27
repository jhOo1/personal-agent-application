# One new deployment on all 18 strict beneficial-use roots

Same exposed sources, new physical calls from the Query router through final grading. All assigned cases were retained, including earlier successful cases. Actor output caps matched across conditions. Strict pass requires rating 3. Each grader sees the full original memory and final answer. Qwen and GPT refer to project-specific adaptations.

| Method | Delivered / 18 | GPT pass/fail/unknown | Qwen pass/fail/unknown |
|---|---:|---:|---:|
| SELECTED | 18 | 18/0/0 | 14/3/1 |
| FULL | 18 | 18/0/0 | 18/0/0 |
| RUBRIC | 17 | 17/0/1 | 14/2/2 |
| S_first | 18 | 18/0/0 | 14/3/1 |
| R_first | 18 | 18/0/0 | 15/2/1 |

| Paired comparison | Judge | Wins/losses/ties/unknown | Bounds on net wins |
|---|---|---:|---:|
| SELECTED vs FULL | GPT | 0/0/18/0 | 0 to 0 |
| SELECTED vs RUBRIC | GPT | 0/0/17/1 | 0 to 1 |
| S_first vs R_first | GPT | 0/0/18/0 | 0 to 0 |
| SELECTED vs FULL | Qwen | 0/3/14/1 | -4 to -3 |
| SELECTED vs RUBRIC | Qwen | 1/2/12/3 | -2 to 1 |
| S_first vs R_first | Qwen | 1/2/13/2 | -2 to 0 |

S_first and R_first use the other method's delivered answer when the primary did not deliver. They do not grant extra generations or look at a grade. FULL uses the GEPA generator and all original sources. RUBRIC uses the full-history author defense. The branches in this study were not a real-time latency experiment.

Physical requests: 196. Status: {'OK': 195, 'FAILED_DELIVERY_UNKNOWN': 1}. Reported tokens: 1,060,025; unknown usage: 1. The six original missing SELECTED outputs are retained in the old deployment.

This is a development repeat on the same source groups and not a statistically independent or official Kimi/Vertex confirmation. A matched observed tie would not establish population noninferiority. No official leaderboard result follows.

[Frozen protocol](PROTOCOL.md) · [Execution](trial.py) · [Aggregate details](SUMMARY.json) · [Case reconstruction](inspect_answers.py)
