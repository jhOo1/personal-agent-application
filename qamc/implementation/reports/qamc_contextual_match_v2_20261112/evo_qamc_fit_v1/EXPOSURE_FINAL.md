# Fixed-Actor memory exposure results

All 162 development assignments settled. The three endpoints use the same Scope Actor, task facts, no-history plan and generation configuration. The only changed input is empty, selected or full original history. Ordinary Gate predicted an endpoint before any new answer or score. Its exact precommitted choice supplies the delivered answer without re-generation. Two tasks have no eligible saved Scope generation, and two of the 160 issued Gate requests have no valid policy. Report original project-adapted grades with separate availability and Judge sensitivities.

| All-method common score | Archived specialist | OFF | SELECTED | FULL | Ordinary Gate |
|---|---:|---:|---:|---:|---:|
| RPEval Match, 122/126 tasks | 387/624 | 314/624 | 294/624 | 278/624 | 300/624 |
| RPEval OPB / UPB / FM | 127 / 110 / 25 | 62 / 251 / 123 | 176 / 124 / 66 | 171 / 154 / 67 | 148 / 153 / 63 |
| BenchPreS AAR, four tasks, attributes only | 4/4 | 0/4 | 1/4 | 3/4 | 0/4 |
| BenchPreS MR, same four tasks | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 |
| BenchPreS completeness, three complete common rows | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| PersistBench CD | 12/12 | 12/12 | 12/12 | 11/12 | 12/12 |
| PersistBench SYC | 3/4 | 4/4 | 4/4 | 2/4 | 4/4 |
| PersistBench strict beneficial use | 13/13 | 1/13 | 13/13 | 13/13 | 13/13 |

The specialists are IPE-C, Strong Gate and PB_RUBRIC. The intersections differ from the [previous three-arm completion](EXPANSION_FINAL.md), so raw counts should be compared within each table. The original project Judge adaptations, single deployment and exposed development material preclude official comparable SOTA claims.

## Activation trade-off and ordinary Gate failure

- On the 62 common RPEval tasks where the archived IPE-C omits history, OFF improves SELECTED from 114/278 to 171/278, versus archived 199/278. On the other 60 common tasks OFF declines from 180/346 to 143/346, with UPB increasing from 65 to 170.
- Of the 62 tasks in the archived off stratum, the ordinary Gate still exposes selected history on 29. Across those 29 actual Gate responses it records 30/133, while their exactly paired OFF answers score 79/133. The outstanding error is mostly deciding to expose when closing was beneficial, with other errors in the opposite direction on legitimate use.
- RPEval all-A OFF versus SELECTED is 151/236 versus 80/236. B-only goes 31/84 versus 41/84, and the C-containing task slice goes 132/304 versus 173/304. The gate recovers some all-A Match (94/236) but loses B-only Match (35/84). It does not combine the endpoint strengths.
- On the single available BenchPreS profile the ordinary Gate chooses OFF on all four tasks. FULL retains substantially more applicable formatting in this controlled generation than SELECTED, without additional observed MR. Other expression types and profiles remain untested by this expansion.
- Scope with SELECTED, FULL and Gate all preserve the 13 jointly scored strict BU tasks. OFF loses 12 of those passes. FULL raises the cross-domain and sycophancy failure counts on the common tracks. Thus a successful safety component alone cannot substitute for positive utilization.

## Headroom and scoring sensitivity

The per-task exact saved-answer maximum of the three endpoints is 371/624. The same maximum is possible while requiring paired OPB, UPB and FM no worse than SELECTED. Eighteen archived answers beat all three saved endpoints on Match. On the 58 common tasks with no known flag in any endpoint or the archived grade, the maximum is 211/332 against IPE-C 207/332; SELECTED is 192/332 and the ordinary Gate 188/332. A gate optimized on the existing candidate set has room for development, and measured headroom depends on scoring sensitivity. The numerical maximum uses reference scores only after generation and is not the performance of an algorithm.

On the jointly unflagged archived IPE-C-off slice, OFF is 94/121, SELECTED 84/121, ordinary Gate 82/121 and IPE-C 98/121. On the unflagged all-A slice OFF is 81/92 versus IPE-C 75/92, while Gate and SELECTED are both 64/92. Main results and original flag handling remain unchanged. [Two-batch examples of Judge conflicts](EXPOSURE_TWO_BATCHES.md)

Retain selective Scope as a baseline and reject the ordinary task-level Gate as an upgrade. Test a controller that distinguishes a source's concrete contribution to an already requested decision, valid expression implementation and unnecessary influence. Use the preexisting 40-task fit allocation for development feedback, and use the matched endpoints to diagnose possible improvement before spending on a new generation mechanism. The next method must protect B/C, formal completion and strict BU, and should not repeat DCR's fragment isolation under a new name. [DCR qualification](DCR_ASSEMBLY_QUALIFICATION.md)

703 physical requests were dispatched, including 160 Gate, 235 Actor and 308 grading. 702 transports returned, one Gate delivery is unknown, and 3,101,353 tokens were reported. All exact successes were reused where compatible; there were no automatic retries. [Aggregate JSON](EXPOSURE_FINAL.json) · [Frozen protocol](EXPOSURE_CONTROLS_PROTOCOL.md)
