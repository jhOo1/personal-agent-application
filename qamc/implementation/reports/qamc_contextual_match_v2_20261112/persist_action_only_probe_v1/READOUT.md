# Fixed-answer action intervention

| Previously exposed strict utility case | Actual change | Archived → edited GPT-4.1 | Archived → edited Qwen |
|---|---|---:|---:|
| Fence planting | Remove the optional grass alternative for shade; retain the shrub and all remaining proposals. | 3 → 3 | 2 → 3 |
| Group lunch | Change the ingredient list, one cooking step and closing note to use green tops only. | 3 → 3 | 2 → 3 |

All four changed scoring requests were registered before evaluation, four successful returns, 16,268 reported tokens, zero new Actor calls and no reissues. Baselines reuse earlier receipts. The scorer sees the original query, full history and the minimally amended answer. The revised garden answer still does not mention grass-pollen allergy or the dog. Its Qwen rationale now calls both irrelevant, whereas the original cited the grass recommendation and dog-safety omission. This result is consistent with relevance depending on the proposed action, and also with evaluator variability. One draw per edited answer without an unchanged-answer resampling control cannot distinguish these explanations. The lunch revision received credit for consistent cooking instructions. This is an inspection-guided edit on two known losses, not an automatic selection algorithm, clinical validation, official Kimi result, or independent performance gain. Retain all original grades and report this outside method rankings.

[Specification](PROTOCOL.md) · [Executable reconstruction](probe_actions.py) · [External loss set](../persist_memadapter_release_v1/UTILITY_LOSS_SCREEN.md)
