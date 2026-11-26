# BenchPreS repeat-sampling first wave

This is an interim result on 8 of the fixed 48 exposed development tasks. Both methods use temperature 1 for generation and the same Qwen grading adaptation. Each evaluable method/task runs three independently registered draws, conditional on its frozen input. The experiment uses the temperature and repeat setup of the BenchPreS proceedings §4.1 and the Figure 11 Selectivity defense. The Judge and task coverage differ from the proceedings evaluation. [Frozen protocol](PROTOCOL.md) · [BenchPreS proceedings](https://aclanthology.org/2026.emnlp-main.1040/)

| Common valid pairs | Measure | Strong Gate | Selectivity |
| --- | --- | ---: | ---: |
| 19 task-draw pairs, 7 tasks | Misapplication | 0/61 | 4/61 |
| 19 task-draw pairs, 7 tasks | Appropriate application | 27/34 | 24/34 |
| 19 task-draw pairs, 7 tasks | Non-bold appropriate application | 13/20 | 15/20 |
| 19 task-draw pairs, 7 tasks | Bold appropriate application | 14/14 | 9/14 |
| 19 task-draw pairs, 7 tasks | Mean completeness | 87/19 | 84/19 |
| 15 pairs, 5 tasks with all three draws scored on both arms | Misapplication | 0/51 | 3/51 |
| 15 pairs, 5 tasks with all three draws scored on both arms | Appropriate application | 19/24 | 15/24 |
| 15 pairs, 5 tasks with all three draws scored on both arms | Non-bold appropriate application | 7/12 | 8/12 |

Overall AAR improves in this wave because Gate realizes five more appropriate bold attributes, offset by two fewer non-bold applications. Completeness is higher in the observed available pairs. The first wave was frozen for operability and provides only descriptive evidence. It cannot establish a full-panel advantage, cross-profile generalization, or a native ranking. [Aggregate replay and missing bounds](WAVE0_REPLAY.json)

All 45 executable Actor positions and 270 Judge positions succeeded at the transport level. The Actor receipt IDs are distinct, and each of the 15 executable method/task cells gives three distinct answers. Two grade contracts are invalid, one Strong Gate completeness output and one Selectivity attribute output. The pre-existing missing Strong Gate wire adds three unavailable draws for one of the eight tasks. The ledger records 315 requests, 426,974 reported tokens, zero unknown usage and zero retries. The replay is byte-identical. No data was drawn from the sealed set.

Wave 1 started via the existing sequential continuation after first-wave operability was verified. Subsequent waves use the same frozen order and scoring, without a decision based on interim scores.
