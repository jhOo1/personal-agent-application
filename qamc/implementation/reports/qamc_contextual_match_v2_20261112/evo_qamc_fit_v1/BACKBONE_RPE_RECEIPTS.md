# RPEval receipt settlement while the other crossover grades run

All 24 physical RPEval grades were returned and replayed by exact request identity. The original full RPEval candidate pool determines the rating and Match position count in every arm; the visible subset affects the generation request only. This is the eight-source exposed development stratum of the frozen crossover. BenchPreS and PersistBench are not part of this preliminary score table.

| Same-source comparison | Matched tasks | Match, first → second | All-assigned Match difference bound |
| --- | ---: | ---: | ---: |
| Qwen Scope → DeepSeek Scope, selected history | 7 | 18/35 → 18/35 | [−2, 2] |
| Qwen Direct → DeepSeek Direct, selected history | 4 | 9/22 → 12/22 | [−5, 12] |
| Qwen Scope OFF → selected | 8 | 26/39 → 20/39 | −6 |
| Qwen Direct OFF → selected | 8 | 22/39 → 17/39 | −5 |
| DeepSeek Scope OFF → selected | 4 | 14/18 → 11/18 | [−17, 8] |

For Qwen Scope, the all-A stratum falls from 16/16 to 9/16 when supplying selected evidence, B-only rises from 5/13 to 6/13, and contains-C remains 5/10 over all positions in those tasks. These are observed project grades rather than behavioral adjudication or labels of individual evidence positions.

On nonempty selected histories, the observed four-cell difference in the effect of history on Match is zero under Scope (3 matched roots, 12 positions) and Direct (1 root, 6 positions). The corresponding bounds over the seven eligible roots are [−11, 14] and [−11, 20]. No RPEval root has all eight terminal answers. There is limited evidence of a better Direct score on its surviving cases, insufficient evidence of a stronger history-use effect, and no basis to select a DeepSeek config from this RPEval slice. Judge and transport limitations remain explicit. The two cached Qwen Scope/Direct prompt contracts should be judged on their observed behavioral shifts, not by assuming a missing grade would favor the faster service.

[Read-only receipt replay](backbone_receipt_replay.py) · [Earlier answer-side checks](BACKBONE_BEHAVIOR_EVIDENCE.md)
