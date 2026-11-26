# BenchPreS repeated evaluation halfway checkpoint

Three of the six frozen waves have settled. There are 24 allocated exposed tasks, with 66 common scored draws across 23 tasks in 10 profile groups. Strong Gate and the published Figure 11 Selectivity adaptation use the same Qwen3.8 Flash Actor alias and temperature 1, with the original method-specific Actor prompts and a common Qwen Judge adaptation. The proceedings use DeepSeek-R1 for scoring. [Protocol](PROTOCOL.md)

| Common paired metric | Strong Gate | Author Selectivity |
| --- | ---: | ---: |
| Misapplication | 1/217 | 25/217 |
| Appropriate application | 97/113 | 79/113 |
| Appropriate bold application | 40/41 | 25/41 |
| Appropriate non-bold application | 57/72 | 54/72 |
| Completeness | 315/66 | 310/66 |

Across the 20 tasks scored for all three draws on both arms, MR is 1/201 vs 22/201, AAR is 86/99 vs 67/99, non-bold AAR is 48/60 vs 44/60, and completeness is 287/60 vs 282/60. The common-pair MR advantage occurs in nine of ten profiles with one tie. The non-bold difference is positive in two of seven profiles with five ties. The interim profile bootstrap for non-bold AAR spans 0 to +12.5 percentage points. Draws share tasks, profiles and scoring rules. These are descriptive development results. [Replay and missing bounds](WAVES012_REPLAY.json) · [Profile sensitivity](WAVES012_PROFILE_TRACE.json)

Of the 25 Selectivity misuse labels, 17 are inappropriate nicknames. All 17 appear as exact words. Two additional Selectivity answers use the corresponding literal nickname although the Judge labels it unobserved. Gate has zero literal inappropriate nicknames on the same 66 positions. The one Gate misuse is an expressive-tone label on a hearing-accommodation request. Its text uses appreciation language without the explicit emphasis markers tested in the spot check. That observation leaves the tone label open to interpretation. [Misuse trace](WAVES012_MISUSE_TRACE.json)

All 72 appropriate non-bold positions have their original expression visible to both Actors after lexical normalization, including in the selected memory block for Gate. The arms both receive credit on 49, and neither receives credit on 10. Two distinct task–attribute positions are missed by both methods in all three draws, the rental-history brevity preference and the objective-information preference in an insurance-claim appeal. This suggests that improving source availability alone has little room on these observed pairs. [Exact delivery trace](WAVES012_DELIVERY_TRACE.json)

There are 981 physical requests in the three settled waves, with 980 transport successes, one unknown Actor delivery and usage, two invalid scoring contracts, and zero automatic retries. Reported usage totals 1,384,986 tokens. One older task lacks a Strong Gate Actor wire and accounts for three unavailable draws in the settled slice. On 68 successful Actor pairs, Gate uses 523,695 input and 641,183 total tokens, and Selectivity uses 160,423 input and 318,475 total tokens. These costs omit selector and scoring. Wave four began through the frozen sequential runner. No changes to allocation, scoring, or sealed data. [Cost replay](WAVES012_COSTS.json)
