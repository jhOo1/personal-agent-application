# RPEval archived endpoint behavior check

Frozen source groups: 22. Requests: 22. Receipt statuses: {'INVALID_JUDGE_OUTPUT': 21, 'OK': 1}. Reported tokens: 85185. Unknown usage: 0. Valid paired assessments: 1. History enabled on 1 of these. No new Actor answers, native scores or human judgments.

|Author intent|Paired determinate positions|Task only|Full history|IPE-C|Expected at same opening rate|
|---|---:|---:|---:|---:|---:|
|A|5|4|2|2|2.00|
|B|0|0|0|0|0.00|
|C|0|0|0|0|0.00|

Numerators count behavior matching the author intent in both-endpoint determinate positions. For A, either no use or an independently task-justified decision qualifies. B requires soft use, C requires a binding constraint. Unknowns and indeterminate task-justified B/C judgments are excluded pairwise. The reference is the expectation over uniform random assignment of the same count of open tasks; it uses no labels. This panel deliberately balances rare route strata. Its old native-adapted Match was 60/118 for IPE-C, 64/118 task only and 72/118 full history. Behavior judgments share the gpt-4.1 alias with the project scorer. Assessment availability depends on strict JSON and literal evidence checks. No imputation.

TASK_ONLY: complete 1/1, requirement violations 0, unsupported fact violations 0.

RPR_PAPER_FULL: complete 1/1, requirement violations 0, unsupported fact violations 0.

IPE_C: complete 1/1, requirement violations 0, unsupported fact violations 0.

The single valid pair provides no estimate of routing reliability. Invalid responses included skipped memory IDs and incomplete response schemas. Archived failures were kept. Retain RPEval and PersistBench as primary evaluations of history activation, and report BenchPreS as both a positive strong-Gate reference and an expression/completeness boundary. The proposal changes prioritization only. No benchmark was removed or added. See [the exact-request comparison](QUERY_ORACLE.md).
