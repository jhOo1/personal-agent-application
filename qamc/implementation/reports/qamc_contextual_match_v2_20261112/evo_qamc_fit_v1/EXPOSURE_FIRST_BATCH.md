# First matched-Actor exposure batch

The first 57 of 162 assigned exposed development tasks settled. The ordinary prediction per task was frozen before new endpoints. The Actor, no-history task plan, task facts, settings and Judge protocol match across OFF, SELECTED and FULL. These are the existing project scoring adaptations.

| Common measure | Archived specialist | OFF | SELECTED | FULL | Ordinary Gate |
|---|---:|---:|---:|---:|---:|
| RPEval Match, 41/42 tasks | 128/205 | 101/205 | 101/205 | 83/205 | 100/205 |
| RPEval OPB / UPB / FM | 37 / 37 / 7 | 19 / 83 / 35 | 53 / 43 / 20 | 51 / 64 / 18 | 40 / 57 / 19 |
| BenchPreS AAR, 4 tasks and one profile, attributes only | 4/4 | 0/4 | 1/4 | 3/4 | 0/4 |
| BenchPreS MR, same four tasks | 0/16 | 0/16 | 0/16 | 0/16 | 0/16 |
| BenchPreS completeness, 3 complete all-arm rows | 15/15 | 15/15 | 15/15 | 15/15 | 15/15 |
| PersistBench CD pass | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 |
| PersistBench SYC pass, 1/2 all-arm common | 0/1 | 1/1 | 1/1 | 0/1 | 1/1 |
| PersistBench strict beneficial use | 5/5 | 0/5 | 5/5 | 5/5 | 5/5 |

On the 20 common RPEval tasks where archived IPE-C turns off history, changing actual visibility from SELECTED to OFF improves 50/96 to 62/96 and lowers OPB from 22 to 6. Archived IPE-C is 72/96. The matched intervention recovers 12 of the 22 positions separating SELECTED from IPE-C in this stratum. On the 21 tasks where IPE-C keeps history, OFF instead drops from 51/109 to 39/109 and UPB rises from 26 to 59. The overall Match tie between OFF and SELECTED therefore combines opposite effects. At fixed backbone, the Actor's memory exposure is an important cause of the observed trade-off; individual text changes and score attribution still require separate checks.

On 19 all-A common tasks, OFF, SELECTED, FULL and Gate reach 54, 37, 22 and 41 of 83 positions. On six B-only common tasks the same methods obtain 11, 16, 16 and 12 of 37. On 16 C-containing common tasks they reach 36, 48, 45 and 47 of 85. These denominators include all author positions in each task subset. The ordinary Gate does not capture the OFF gain on the IPE-C-off stratum and has higher aggregate UPB than SELECTED. When removing pairs with existing judge flags, Gate has 84/145 versus SELECTED 81/145 on 29 common RPEval tasks, with UPB 26 versus 24. Preserve that limited sensitivity result.

FULL recovers two additional instances of appropriate formatting versus SELECTED on BenchPreS, while OFF and the ordinary Gate miss all four. This profile does not support a universal formatting claim. OFF also fails all five common strict-beneficial-use tasks in PersistBench, and both memory-bearing endpoints pass them. The same gate behavior can therefore be beneficial on inapplicable history and harmful on needed history. The next mechanism must distinguish these classes using actual visible task and source properties.

There are 368 physical requests accounted for at this checkpoint, including all 160 frozen-roster Gate requests and 208 first-batch endpoint requests. There are 1,339,874 reported tokens, with 367 successful transports and one unknown delivery from Gate. The second batch is running. No inference calls were made to produce this report.

## Headroom of the saved answer set

On the 41 common RPEval tasks an offline selector given the grades could obtain 118/205 by selecting the best saved answer from OFF, SELECTED and FULL. It can attain the same total while requiring no higher OPB, UPB or FM than SELECTED on each chosen task. Scope alone scores 101/205, the ordinary Gate 100/205 and IPE-C 128/205. Five tasks have no saved endpoint that reaches the archived answer's Match. This is a ceiling for choosing among the exact saved outputs, not a limit on new generations or a deployable method.

All 17 positions of headroom over SELECTED in this batch occur among the archived IPE-C-off tasks and, independently, among all-A tasks. The saved endpoints provide no Match headroom above SELECTED on the C-containing or B-only tasks. Better activation could therefore recover part of the gap, but a chooser of these answers cannot remove the remaining ten-position deficit. Changing execution where useful history is visible remains a separate hypothesis to test.
