# Two batches of matched-Actor exposure controls

The first 110 of 162 development assignments have settled. The comparison holds the original Scope Actor, task facts and task-only plan fixed across the three exposures. The task-level Gate cannot revisit its decisions after seeing outcomes. The third batch is running.

| Common measure | Archived specialist | OFF | SELECTED | FULL | Ordinary Gate |
|---|---:|---:|---:|---:|---:|
| RPEval Match, 81/84 tasks | 253/407 | 189/407 | 200/407 | 182/407 | 199/407 |
| RPEval OPB / UPB / FM | 85 / 65 / 18 | 46 / 175 / 83 | 111 / 82 / 42 | 108 / 106 / 49 | 96 / 98 / 40 |
| BenchPreS AAR, all four tasks, attribute only | 4/4 | 0/4 | 1/4 | 3/4 | 0/4 |
| PersistBench CD, 8 common tasks | 8/8 | 8/8 | 8/8 | 7/8 | 8/8 |
| PersistBench SYC, 4 common tasks | 3/4 | 4/4 | 4/4 | 2/4 | 4/4 |
| PersistBench strict BU, 7 common tasks | 7/7 | 0/7 | 7/7 | 7/7 | 7/7 |

With no history exposure, RPEval all-A Match improves from 57/145 to 82/145, while on the archived IPE-C-retain subset it drops from 127/248 to 97/248. The ordinary Gate captures neither an aggregate Match gain nor the all-A endpoint's protection. The apparent upper bound of choosing from the saved OFF, SELECTED and FULL answers is 230/407; IPE-C is 253/407. The ordinary Gate scores 199/407. The upper bound uses scores in evaluation only.

## Judge sensitivity affects the interpretation of the remaining gap

| Paired RPEval slice | Positions | Archived IPE-C | OFF | SELECTED | Gate | Best of the three saved endpoints |
|---|---:|---:|---:|---:|---:|---:|
| All common, no known flags in any endpoint | 201 | 125 | 105 | 121 | 120 | 127 |
| IPE-C clears history, no known flags in any endpoint | 59 | 52 | 52 | 47 | 47 | 52 |
| IPE-C retains history, no known flags in any endpoint | 142 | 73 | 53 | 74 | 73 | 75 |

The initial conclusion that the saved endpoints cannot catch IPE-C is true of the recorded main scores. It changes on the 37 jointly unflagged tasks, where their offline maximum is slightly above IPE-C. The 37-task restriction is a sensitivity analysis, not a preferred test set. In four of the largest recorded OFF losses in the IPE-C-clear stratum, the fresh OFF got zero and was itself flagged as having bias fields incompatible with the all-A labels. The cases include a father's birthday, dormitory instruments, family living-room furnishing and a family Yunnan itinerary. Both the old task-only answer and fresh OFF answer are verified no-history generations; their exact prompts and structure differ. In the older IPE-C-clear stratum, on the 15 jointly unflagged tasks the matched OFF ties the archived endpoint while the ordinary Gate does not recover the gap. These facts support treating selection quality and scoring noise as separate problems. The original grades and flags remain unchanged.

The cumulative checkpoint includes 536 physical requests and 2,192,580 reported tokens, with 535 returned transports and the one existing Gate delivery of unknown status. All 168 additional second-batch transports returned. No new calls were needed for this analysis. Official publication comparability remains outside the current adapted scoring protocol.
