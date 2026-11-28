# RPEval scoring settled for the first two fit policies

The RPEval grader made 30 requests and returned 30 usable results. The 16 assigned tasks include one missing generation pair. The other 15 tasks share 88 evaluated positions across both new policies and archived IPE-C. This is the exposed fit panel and uses the project's frozen RPEval grading adapter.

| Same tasks | IPE-C | Generic plan with full history | Action plan with full history |
|---|---:|---:|---:|
| Match | 46/88 | 33/88 | 35/88 |
| OPB severity | 15 | 32 | 34 |
| UPB severity | 19 | 14 | 13 |
| FM severity | 3 | 10 | 8 |
| All-A Match | 7/25 | 0/25 | 0/25 |
| B-only task Match | 26/38 | 19/38 | 21/38 |
| C-containing task Match | 13/25 | 14/25 | 14/25 |
| Match without known score flags | 31/58 | 25/58 | 26/58 |

The executable action instructions offset a little of the generic policy's loss while increasing OPB further. The zero Match on all-A tasks under both new policies is the clearest issue. Both planners and the final Actor see the full history. This design cannot determine which exposure caused the loss. The fixed-budget task-only planning arm moves initial exposure after planning while the direct selection arm changes final exposure. Their results will distinguish these hypotheses more directly. The two new policies do not replace IPE-C on the evidence available.

The 30 scoring requests used 127,635 reported tokens, with no unknown usage at this scoring stage. The [paired scores](RPE_STAGE.json) were replayed without new requests by matching the original scoring manifest and receipts. Other benchmarks and matched controls are reported separately when their scoring completes.
