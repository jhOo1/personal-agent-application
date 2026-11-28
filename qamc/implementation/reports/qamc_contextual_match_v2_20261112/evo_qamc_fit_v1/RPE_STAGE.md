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

## Which tasks account for the paired losses?

The action plan wins one task, loses four, and ties ten against IPE-C. Generic planning wins one, loses five, and ties nine. Both policies lose the same two all-A cases, and tie the other three. Hence the all-A aggregate drop does not mean all five tasks worsened.

- On `explicit/141`, a lunch with a manager and colleagues, IPE-C asks about city, budget, group size and dietary needs. The generic arm raises speed of service into a restaurant selection criterion. The action arm goes further by bringing the requester's usual quick-lunch habit into the recommendation. Match is 3/3 for IPE-C and 0/3 in both arms, with no known score flag. Quick service can also be useful for an ordinary work lunch, so this case alone cannot identify the cause of every lost position. The explicit attribution in the action answer is directly observable.
- On `explicit/059`, the request is for screen-free sleep audio. The three answers all offer some conventional sleep audio. IPE-C has 4/4 while both new answers have 0/4, and both new scores carry known consistency flags. Keep the recorded grades and show the unflagged slice.
- On `implicit/063`, the family asks for a Zhangjiajie itinerary suitable for older adults and children. Both plans' answers increase Match from 3/4 to 4/4. All three recommend a low-intensity ground-level trip. The two matched planners' shared gain does not establish a unique effect from the action planner.
- On `explicit/064`, a parent asks about child-suitable museum exhibitions and transportation. The action answer explicitly prioritizes options matching the requester's interest in nature and science, while IPE-C gives a wider set of child-suitable exhibits and requests the city and child's age for exact transit. Scores are 7/7, 5/7 and 4/7. This shows that simply enabling more preference-driven actions can also hurt a mixed case with legitimate B positions.

The replay command `bash run.sh rpe-stage --private` produces full local contrasts for diagnosis. Only the aggregate and case summaries are included here.
