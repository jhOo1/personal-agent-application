# How much could choosing the Actor recover?

Post-hoc diagnostic on the frozen BenchPreS panel. Every comparison uses the same complete draw pairs. Selection optimizes the indexed preference only. Ties keep Qwen. The task oracle uses all scored draws for the task, including the evaluated draw. The other-draw rule uses only earlier or later scored draws of that identical task and excludes the evaluated draw. Neither rule is available for a new task at inference.

| Cohort | Policy | DeepSeek uses / pairs | Indexed follows | AAR numerator | MR numerator | Completeness total |
|---|---|---:|---:|---:|---:|---:|
| targets | Qwen | 0/15 | 2 | 25 | 0 | 64 |
| targets | DeepSeek | 15/15 | 3 | 27 | 0 | 68 |
| targets | Task oracle | 6/15 | 4 | 27 | 0 | 61 |
| targets | Other draws | 4/15 | 2 | 25 | 0 | 62 |
| controls | Qwen | 0/23 | 23 | 41 | 0 | 112 |
| controls | DeepSeek | 23/23 | 22 | 38 | 0 | 106 |
| controls | Task oracle | 0/23 | 23 | 41 | 0 | 112 |
| controls | Other draws | 0/23 | 23 | 41 | 0 | 112 |

Across all 32 fixed assignments to the five target tasks, the indexed maximum is 4/15; its tied assignments span completeness 60–64 points. Requiring aggregate target completeness and AAR at least Qwen's and MR at most Qwen's leaves an indexed ceiling of 4/15. These are hindsight bounds.
