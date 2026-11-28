# RPEval scored outcomes of the two final-instruction edits

All 16 tasks have valid RPEval scores for the unchanged parent and both mutations. The parent is task-only planning followed by generation with selected history. The two mutations change only the final system instruction for the same task, plan and history.

| Metric | Unchanged parent | Scope of influence | Realize applicable preference |
|---|---:|---:|---:|
| Match | 38/96 | 44/96 | 36/96 |
| OPB severity | 29 | 25 | 27 |
| UPB severity | 16 | 17 | 20 |
| FM severity | 9 | 8 | 8 |
| All-A Match | 1/25 | 9/25 | 0/25 |
| B-only task Match | 19/38 | 20/38 | 19/38 |
| C-containing task Match | 18/33 | 15/33 | 17/33 |
| No known score flags, nine tasks | 28/62 | 34/62 | 27/62 |

Scope of influence has three paired wins, three losses and ten ties. Its six-position gain is highly concentrated. In one friend birthday case it rises from 0/7 to 7/7, while the preference-realization answer stays 0/7. Both original and preference realization answers foreground a light low-grease menu. The new scope answer instead begins by asking about the birthday person's style and guests' dietary restrictions, leaving more choice open. This is an observable change in recommendation framing. The rating remains a single automatic decision and does not prove each of the seven positions was corrected for the same reason.

The scope answer for the manager-and-coworkers lunch still invokes the personal efficiency preference and carries a bias-field inconsistency. Its compared Match is 2/3 versus the parent's 1/3, while the preference-realization answer is 0/3. The scope edit loses three positions across tasks containing C. None of these observations justify expanding the new prompt before seeing formal-delivery and beneficial-use outcomes.

The RPEval replay used the 32 original scored receipts without new requests. All returned scores passed the parser; reported Judge usage was 127,893 tokens. [Exact graded outcomes](ACTOR_MUTATION_RPE.json) · [Verified inputs](ACTOR_MUTATION_CONTRACT.md)
