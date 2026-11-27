# Comparing graders after all three published risk generations

Use the identical three authored external answers per root and model. The first grades were reused. All 60 remaining project GPT-4.1 requests returned valid scores, using 566,350 reported tokens. No new Actor or Kimi calls. Published Kimi ratings come from the author's unfiltered baseline release.

| Risk track | Roots × models | Released / project pass on first draw | Released / project pass across all three | Same three-draw decision |
|---|---:|---:|---:|---:|
| Cross-domain | 4 × 5 | 16 / 13 | 9 / 11 | 16/20 |
| Sycophancy | 2 × 5 | 5 / 5 | 1 / 3 | 8/10 |

A single draw suggested the project grader was stricter on cross-domain; the full track aggregation changes that direction. Among ten cross-domain model pairs, one strictly reverses: Claude Sonnet 4.5 vs Grok 4.1 Fast goes from 2 vs 1 passes under released ratings to 2 vs 3 locally. Three pairwise differences become ties and one tie breaks. Under sycophancy three ties break with no strict reversal. Pair comparisons share roots and models.

Strict utility uses one draw. Of ten external-model pairs on seven roots, four preserve their strict order, five former differences become ties, and one remains tied. Keeping that track separate, the relaxed threshold passes every answer. See [single-generation model counts](../persist_released_grade_agreement_v1/MODEL_ORDER.json).

This calibrates the reliability of rankings on these external answers only. The new comparisons do not supply official grades for QAMC and do not warrant a constant score correction. [Frozen protocol](PROTOCOL.md) · [All model totals and paired decisions](RESULTS.json)
