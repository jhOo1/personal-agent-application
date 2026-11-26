# BenchPreS early repeat waves: what the misuse gap contains

This audit checks the exact submitted Actor output, its attribute grading request, the returned label, and the frozen evaluation attributes. It covers all 136 inappropriate attribute positions per arm across 42 paired draws on 15 exposed tasks. It changes no score and makes no model request. [Paired result](WAVES01_READOUT.md) · [Trace data](WAVES01_MISUSE_TRACE.json) · [Replay script](trace_misuse.py)

| Inappropriate attribute | Paired positions | Strong Gate flagged uses | Author Selectivity flagged uses |
| --- | ---: | ---: | ---: |
| Nickname | 42 | 0 | 8 |
| Emoji | 13 | 0 | 2 |
| Emotionally expressive tone | 6 | 0 | 2 |
| Other | 75 | 0 | 0 |
| Total | 136 | 0 | 12 |

All eight flagged Selectivity nicknames appear as exact case-sensitive words in the corresponding answers. Two additional Selectivity answers also contain the specified nickname although the adapted Judge returns `do_not_follow`: one explicitly asks to be called by it in a visa-renewal message, and one includes it in the closing of a civil-attorney message. None of the 42 matched Gate answers contains the corresponding inappropriate nickname. This makes the occurrence difference directly inspectable. The literal diagnostic measures occurrence only. Suitability remains an author evaluation label, and the original Qwen scores remain the main adapted comparison.

The 12 flagged Selectivity uses come from 11 distinct task–attribute positions. Seven positions were flagged once in three scored draws, three once in two scored draws, and one twice in three scored draws. None was flagged in all three. Repeated draws expose variability that a single generation misses. This early gap is concentrated on formal presentation and naming conventions. It does not establish an effect on substantive task decisions, universal misuse prevention, or independent generalization.

The next manuscript comparison should keep three quantities visible: aggregate MR, the category contribution to MR, and appropriate non-bold realization. The first estimates performance under the adaptation. The second explains which behaviors account for much of that estimate. The third checks where improvement still has to come from.
