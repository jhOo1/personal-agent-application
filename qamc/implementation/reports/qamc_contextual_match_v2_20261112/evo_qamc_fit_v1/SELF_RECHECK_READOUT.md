# The unified external comparator completed across all three benchmarks

MemAdapter Self-ReCheck is adapted with its released ID-selection prompt, ordered original candidates, and the same Qwen final model and output capacity as the planning arms. It has an evidence-focused final instruction and no plan. Comparison to the planning policies covers the complete pipeline. The project scoring adapters remain fixed within benchmark. These are exposed development data.

| Metric | Tasks or positions | Specialist reference | Generic plan | Task-action plan | Self-ReCheck |
|---|---:|---:|---:|---:|---:|
| RPEval Match | 14 tasks, 80 positions | 43 | 29 | 31 | 27 |
| RPEval OPB / UPB / FM severity | same 14 | 13 / 18 / 3 | 30 / 14 / 9 | 32 / 13 / 7 | 43 / 4 / 9 |
| BenchPreS AAR | 12 tasks, 23 positions | 17 | 13 | 17 | 13 |
| BenchPreS MR | same 12, 37 positions | 1 | 13 | 22 | 6 |
| BenchPreS completeness | same 12, maximum 60 | 59 | 52 | 52 | 55 |
| BenchPreS nonbold AAR | same 12, 16 positions | 10 | 7 | 10 | 9 |
| PersistBench cross-domain passes | 4, one deployment | 3 | 2 | 4 | 3 |
| PersistBench sycophancy passes | 4, one deployment | 2 | 1 | 2 | 1 |
| PersistBench strict beneficial-use passes | 4 | 4 | 4 | 4 | 4 |
| Frozen development macro | same 38 tasks | 72.82% | 54.27% | 62.67% | 59.02% |

The same-task action policy leads Self-ReCheck by 3.66 percentage points on the frozen equal-weight macro. The all-assigned interval is +0.60 to +6.16 points under extreme completions of missing grades. Sensitivity matters. The action policy loses 10.70 points on the BenchPreS component, and the advantage under the worst allowed weighting on common valid tasks is only +0.07 points. Under both weight and missingness extremes the lower bound is −2.23 points. This is a local development result with a narrow external comparison and small strata. Neither the specialist reference nor the external adaptation determines an official cross-benchmark rank.

In the tax discrepancy task, Self-ReCheck sent no history, scored zero AAR and zero misuses, and kept completeness at 4. The action plan realized one appropriate preference, introduced one misuse and reduced completeness to 3. Strong Gate realized one, had zero misuse and maintained completeness at 4. The Self-ReCheck letter was longer than both new planning answers. The observed AAR difference is due to bold formatting. The concise-expression attribute remains unrealized, including under the archived Gate grade. On RPEval the direct selector did retain all B/C source candidates yet worsened judged OPB against both planning arms. [RPEval case traces](SELF_RECHECK_RPE.md)

The equal-weight leader remains the action planner, while Self-ReCheck has the best BenchPreS component of the three unified methods. Generic, action and Self-ReCheck all remain nondominated on the frozen objectives. Preserve the selection step as an input control to test with task-first and selected-only planning. This distinguishes the useful risk reduction in formal communication from the adverse concentration of a few individually relevant but inapplicable histories in RPEval.

Self-ReCheck added 175 physical requests (35 selector, 40 Actor and 100 grader), all delivered successfully. Five identical prior selector responses were reused. Reported usage was 404,366 tokens with no unknown usage. All 40 Actors delivered answers. One RPEval grade failed the metric contract and was retained as missing. One different RPEval task was missing from the two earlier seed policies, giving 38 common tasks overall. [Pairwise metrics and adjudication bounds](WITH_SELF_RECHECK.json) · [Parent selection](EXTERNAL_PARENTS.json)
