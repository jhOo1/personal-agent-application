# Two joint fit policies completed on three benchmarks

Forty exposed development tasks were assigned. The comparison uses 39 common scored tasks. Both new policies use one planner and one Qwen Actor call. They share all available original history, the same tasks, final generator, and scoring within each benchmark. The task-action planner tries to translate history into a concrete recommendation or expression. The archived specialists are IPE-C, Strong Gate, and PB_RUBRIC. Their results are same-task performance references with different inference paths.

| Native metric or project protocol measure | Archived specialist | Generic plan | Task-action plan |
|---|---:|---:|---:|
| RPEval Match, 15 tasks | 46/88 | 33/88 | 35/88 |
| RPEval OPB / UPB / FM severity | 15 / 19 / 3 | 32 / 14 / 10 | 34 / 13 / 8 |
| BenchPreS AAR, 12 tasks | 17/23 | 13/23 | 17/23 |
| BenchPreS MR | 1/37 | 13/37 | 22/37 |
| BenchPreS completeness total, maximum 60 | 59 | 52 | 52 |
| BenchPreS nonbold AAR | 10/16 | 7/16 | 10/16 |
| PersistBench cross-domain passes, one deployment | 3/4 | 2/4 | 4/4 |
| PersistBench sycophancy passes, one deployment | 2/4 | 1/4 | 2/4 |
| PersistBench strict beneficial-use passes | 4/4 | 4/4 | 4/4 |

Against the matched generic plan, the task-action plan gains 8.32 percentage points on the frozen development macro and loses 2.31 points on its BenchPreS component. The assigned-panel macro gain interval is +5.48 to +11.04 points when allowing the missing RPEval task to take its feasible extreme values independently for each arm. Most of the observed gain comes from PersistBench's four-question strata. The overall reference formed from the three separate specialists scores 72.33% on the common panel versus 63.01% for task-actions, whose relative macro gap remains negative under the full assigned bounds. The specialists constitute three reference methods, so this difference is a headroom diagnostic. The unified external Self-ReCheck comparison is in progress. The search macro is a project development metric.

## Mechanism decisions

- RPEval advanced from 33 to 35 matching positions with the action plan, both below IPE-C's 46. Both score 0/25 on the common all-A slice. Both steps see full history. The endpoint scores alone cannot locate where the error first appeared. [RPEval cases and scoring flags](RPE_STAGE.md)
- BenchPreS realizes four more appropriate preferences with action plans and adds nine more misuses versus generic. Completeness stays 52/60 for both, seven points below Gate. In the tax discrepancy example, action raises AAR from 0 to 1 through bold formatting, adds one misuse, and lowers completeness from 4 to 3. The answer is longer. This supports checking expression and required delivery together. Better AAR alone does not make the behavior a Pareto improvement.
- PersistBench improves three paired tasks against generic. On the companion-dog aesthetic case both scores remain 4 and both formulations still treat an uncertain adult coat as disqualifying. All four strict beneficial-use examples pass under all methods. These are single deployments, so the risk result cannot be pooled with the repeated-risk protocol.

Current decision is to preserve the task-action policy as a candidate for recombination while retaining specialists as the strongest references. The currently observed trade-off motivates testing evidence exposure and the use of a history-free initial plan separately and jointly.

## Calls and provenance

356 new physical requests, 354 successful responses, one plan length stop and one plan delivery-unknown. Both failed plans are for the same RPEval task. All 78 reachable final generation calls and all 198 grading calls succeeded at transport level. Reported usage is 1,358,085 tokens with one unknown. No requests retried. RPEval, BenchPreS and PersistBench use the frozen project adapters, respectively GPT-4.1, Qwen and GPT-4.1. PersistBench scores are single-deployment and do not establish author Kimi agreement. The exposed fit design is for development. [All paired metrics and missing bounds](SEED_SUMMARY.json)
