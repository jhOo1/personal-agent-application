# RPEval single-source witnessed replacement, first development result

**19/22 on the frozen historical overlap.** The result passes the initial development target and warrants a default-aware control and protected execution study. It does not establish an independent benefit of literal validation.

| Same 22 tasks | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| RP reconstruction | 17/22 | 0 | 7 | 17 |
| Des2Gen adaptation | 18/22 | 1 | 7 | 23 |
| MemAdapter adaptation | 18/22 | 3 | 3 | 14 |
| Ordinary blind Qwen | 17/22 | 2 | 2 | 15 |
| Witnessed replacement | **19/22** | 1 | 2 | 12 |

The new policy wins two tasks and loses none against RP or ordinary blind selection. It is 2/1/19 against each external adaptation. Match is 2/3 on author A, 8/9 on B and 9/10 on C. RP was 2/3, 8/9 and 7/10. In the strict 21-task comparison without a missing original chooser result, witnessed replacement and MemAdapter are both 18/21, and ordinary selection is 16/21. On all 24 tasks, witnessed replacement, RP, Des2Gen, MemAdapter and ordinary selection have 21, 19, 20, 19 and 19 matches. The primary table uses the prespecified fallback policy and retains the ordinary chooser's delivery-unknown states.

## Actual decisions

- Both choosers fix the plant-protein and winter formalwear misses. The former removes the optional animal protein suggestions. The latter replaces wool and leather suggestions with suitable alternative materials. The winter score does carry one OPB severity point. Its archived rationale says faux leather was outside the original preference, whereas the user's source explicitly says they tend not to choose faux leather. Keep that score and discrepancy separate.
- Compared with ordinary selection, this policy preserves the original passing Rome restaurant answer and winter trip packing list for the parents. In Rome, even the two full answers selected by the competing procedures differ in multiple ways. This case's switch prevention establishes the effect of keeping RP on the saved score and does not prove a single phrase caused the grade. The trip packing task is author A and retains the baseline.
- On the Japanese cuisine task this policy removes the RP fallback that positively offers sushi, sashimi and eel if the user wishes to try seafood, while retaining a substantial cuisine list. Both answer scores were already a match. The switch does not establish that an allergy was known, nor that an unverified broth or topping is seafood-free.
- The program accepts five proposed switches and retains the original answer in 19 cases. Three switches do not change Match on their available archived scores. One of these is the exercise playlist. The supplied quoted song and the source's rhythm preference do not by themselves prove the recording is incompatible. This is a concrete example of the difference between valid provenance and valid semantic judgment.

All **24 new selection requests succeeded**, reporting **125,485 tokens** with zero retries and zero unreported usage. No new Actor, benchmark Judge, human review or sealed-data access. Replay on the same raw responses without the witness validator chooses exactly the same five switches and preserves every score. A default-aware ordinary selection control uses the exact same packets and inference opportunity but does not require a conflict witness. That control and the independent reward-model run settle separately. All figures are exposed development results under project Qwen adaptations, and candidate supply still costs three upstream generations if run from scratch.

[Protocol](PROTOCOL.md) · [Matched result](SUMMARY.json) · [Same proposal before and after validation](UNCHECKED_SUMMARY.json)
