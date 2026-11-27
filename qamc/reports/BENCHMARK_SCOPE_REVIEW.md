# Benchmark scope decision after the crossed Actor comparison

Keep all three development records. Recommend testing task-level history exposure primarily on PersistBench, with RPEval as a second test and BenchPreS as a formal-delivery boundary. This is a proposed change in emphasis after development, not an independent confirmation.

On the seven jointly graded contains-C tasks from the [crossed generation study](../implementation/reports/qamc_contextual_match_v2_20261112/rpe_crossed_full_actor_v1/SUMMARY.json), join the private formal multi-coverage RESULT_ROWS.json by full UID with prefix rpeval/formal_multi_v1/. Use native_fields.match.matched and positions. Each of the following three archived paths has the same Match count on each task: RPR_PAPER_FULL, DES2GEN_FULL and MEMADAPTER_FULL.

|Task|Match for each path|
|---|---:|
|explicit/116|4/6|
|explicit/052|4/6|
|implicit/123|3/5|
|explicit/008|5/7|
|implicit/098|3/6|
|implicit/052|4/6|
|implicit/109|4/6|

All three score 27/42, with zero whole-task matches. Equal totals per task do not establish identical errors, source use, answers or scorer validity. Across three additional archived GEPA variants and the four crossed paths, hindsight selection by task reaches 28/42, with the extra position on implicit/098 (GOAL_EFFECT_GEPA). This is a ceiling for these answers on these seven exposed tasks. No sealed examples or new model calls were used.

The benchmark-removal hypothesis needs evidence that the target behavior or scoring protocol is unsuitable. Failure to improve one endpoint or ceiling effects of a particular pool of answers do not establish contradictory instructions across benchmarks. PersistBench can distinguish suppressing harmful history from losing beneficial use. RPEval tests partial use within a single task. BenchPreS additionally requires realization of an appropriate style in a complete deliverable even when the relevant memory was supplied. Publish all three outcomes even if their roles change. Any replacement should be selected by public task, evidence and scoring suitability before inspecting comparative scores.
