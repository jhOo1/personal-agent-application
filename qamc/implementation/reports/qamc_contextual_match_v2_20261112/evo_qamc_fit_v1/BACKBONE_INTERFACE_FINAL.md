# Backbone × interface × exposure crossover settlement

## Decision

Do not switch the production backbone or replace Scope with Direct based on this run. Holding each interface fixed, DeepSeek produced no observed primary-score improvement in the selected-minus-OFF effect on the matched four-cell sets. The four-cell BenchPreS Direct result was negative. All full-assignment bounds include zero. Native-style score and actual behavior changed on individual cases, and the run had too few complete pairs to establish a practically useful model–interface interaction.

The 18 source groups are all exposed development sources. The base IPE-C, Strong Gate and PB_RUBRIC outputs are archived comparators. The crossover controls are exact previously stored or newly generated responses under each arm's actual contract. The locked judge protocols are project adaptations, not provider-matched official leaderboard comparisons.

## Paired results

| Fixed input comparison | RPEval | BenchPreS | PersistBench |
| --- | --- | --- | --- |
| Qwen → DeepSeek, Scope + selected history | 18/35 → 18/35, 7 roots | AAR 2/2 → 2/2, MR 2/8 → 2/8, 2 roots | 3/3 → 3/3 |
| Qwen → DeepSeek, Direct + selected history | 9/22 → 12/22, 4 roots | AAR 3/4 → 3/4, MR 3/11 → 1/11, 3 roots | 1/3 → 2/3 |
| Scope → Direct, Qwen + selected history | 20/39 → 17/39, 8 roots | AAR 5/6 → 4/6, MR 3/14 → 4/14, 4 roots | 6/6 → 4/6 |
| Qwen Scope OFF → selected history | 26/39 → 20/39, 8 roots | AAR 2/6 → 5/6, MR 0/14 → 3/14, 4 roots | 4/6 → 6/6 |
| DeepSeek Scope OFF → selected history | 14/18 → 11/18, 4 roots | AAR 1/1 → 1/1, MR 0/4 → 2/4, 1 root | 2/3 → 3/3 |

The BenchPreS Qwen Scope history gain comes with total completeness 20→19 over four reports and non-bold AAR 2/4→3/4. Qwen Direct with selected history has completeness 18 over four. The DeepSeek Direct selected model swap shows equal AAR and completeness on its three eligible sources. The lower observed MR does not certify a tradeoff improvement over the frozen roster. For PersistBench, on the fixed Qwen Scope arms the two risk tasks in each category all pass. The OFF losses are both strict BU, 0/2 compared with 2/2 with history. A single score per answer is used here, not FR@3.

### Archived specialist comparisons

With Qwen Scope and selected history, RPEval Match is 20/39 against the archived IPE-C 26/39, BenchPreS AAR is 5/6 against Strong Gate 4/6 with MR 3/14 against 1/14 and completeness total 19 against 20, and PersistBench is tied with PB_RUBRIC at 6/6. DeepSeek Scope selected has RPEval Match 18/35 against IPE-C 24/35 on their seven common tasks. Even awarding every missing DeepSeek position a match leaves its full-assignment difference at most −4. DeepSeek Direct has 2/3 strict scores in the PersistBench intersection with PB_RUBRIC's 3/3; its full-assignment upper bound is −1.

### Difference of history effects when switching backbone

The effect is (DeepSeek selected − DeepSeek OFF) − (Qwen selected − Qwen OFF), conditional on actual non-empty selected history. Bounds hold the originally assigned roster fixed and admit all feasible missing primary outcomes.

| Interface | RPEval, matched roots / effect / bound | BenchPreS | PersistBench |
| --- | --- | --- | --- |
| Scope | 3 / 0 / [−11, 14] | 1 / 0 / [−6, 1] | 3 / 0 / [−3, 2] |
| Direct | 1 / 0 / [−11, 20] | 2 / −1 / [−4, 1] | 2 / 0 / [−2, 4] |

Only one task had all eight valid scores (PersistBench), with zero for RPEval and BenchPreS. No three-domain common aggregate is identifiable. The full paired tables retain OPB, UPB, FM, non-bold, continuity of the registered score and root-level support counts.

## Transport and reproducibility

144 logical Actor variants, 112 final scored logical positions. There were 236 physical requests, 205 successful transports and 31 unknown deliveries, from 30 DeepSeek Actor positions and one BenchPreS attribute grader. Physical requests were 15 Qwen Actor, 70 DeepSeek Actor, 24 RPEval grader, 108 BenchPreS sub-graders and 19 PersistBench grader. There were 413,343 reported tokens and 31 unknown usages, with no resends. Actor failures, valid responses, and score failures retain their original statuses. Qwen archived outputs and same-wire copies do not constitute fresh generations. The evaluator was independently replayed from original receipts and agreed with the complete settlement by answer and parsed score.

[Paired aggregates, bounds and costs](BACKBONE_INTERFACE_RESULTS.json) · [Original freeze](BACKBONE_INTERFACE_PROTOCOL.md) · [Observed task behavior](BACKBONE_BEHAVIOR_EVIDENCE.md) · [Read-only receipt verification](backbone_receipt_replay.py)
