# Moving the recipient action ahead of the same context

**The frozen action-first design does not advance.** Across four common scored tasks, moving the exact same action block produced no change in earned applicable attributes. Rental completeness dropped one point despite unchanged words. The structured writer fell one applicable attribute behind the ordinary one-call writer and the archived Strong Gate.

| Four common tasks, all five arms | AAR | Non-bold AAR | MR | Completeness total |
|---|---:|---:|---:|---:|
| Archived Strong Gate | 7/9 | 5/7 | 0/11 | 19/20 |
| Archived Figure 11 Selectivity adaptation | 7/9 | 5/7 | 0/11 | 18/20 |
| Direct strong writing | 7/9 | 5/7 | 0/11 | 18/20 |
| Same structured answer, context first | 6/9 | 4/7 | 0/11 | 19/20 |
| Same structured answer, action first | 6/9 | 4/7 | 0/11 | 18/20 |

The four render pairs changed block order without changing the text of any block. Both structured renderings used fewer words than the direct message on each common task. None earned a new non-bold credit over the direct writer. All four order comparisons tied on non-bold AAR. This experiment cannot separate unequal adapted grades between otherwise equivalent texts from judge sampling variability, and it does not show whether a human recipient would prefer one order.

## Behavior and coverage boundaries

- **Rental history:** both structured letters include the same timeline and request. Action first still scored completeness 3 compared with 4 for context first. The order manipulation cannot have removed a fact. The structured letters contain 81 words, the direct answer 121. The target non-bold preference was missed in all arms.
- **Annual physical:** both structured renderings present an earlier documented adjustment as a current medication. The ordinary writer also says it is current. A category-first renderer cannot resolve time validity. Both structured renderings lost one applicable attribute relative to direct and Strong Gate.
- **Debt consolidation:** the structured letter made the lender's next actions explicit. Both layouts earned 2/3 applicable attributes, the same as direct and Strong Gate, one behind the adapted external Selectivity answer.
- **Tax discrepancy:** the structured answer was valid JSON with four line breaks in its closing. The original parser's stricter line cap rejected it, so the primary result correctly retains both layouts as missing. The ordinary comparison earned 3/3 AAR versus 2/3 for Strong Gate, but both new raw generations linked the notice to a prize from history without evidence that the notice concerns that prize. This prevents treating the ordinary preference credit as an unambiguous task-quality gain.

Ten Actor requests and 78 scoring requests returned successfully, with 130,269 tokens, no unknown usage and no resend. Settlement replay matched the original 88 requests. The main protocol retains the structural failure and never uses its scores from a modified renderer. A separate recovery uses the same raw response, allowing the extra closing line and preserving unchanged words across the two layouts.

[Main protocol](PROTOCOL.md) · [Main results with missingness](AGGREGATE.json)

## Separate recovery from the saved tax response

Both tax layouts earned AAR 2/3, non-bold AAR 1/2 and MR 0/2. The completeness score was 4 for context first and 3 for action first. On a separate five-task rendering readout that adds this diagnostic, both orders are 8/12 AAR, 5/9 non-bold and 0/13 MR. Completeness is 23/25 context first and 21/25 action first. No change to the primary four-task report or its missing assignment. The two-point total difference is an observation under a single grader draw per rendering.

Twelve newly issued scores returned successfully at 6,581 tokens and zero retries. No new generation. The model response's unsupported association between the tax notice and the historic prize is present in both layouts, irrespective of the completeness change. [Recovery grades](TAX_RECOVERY.json) · [Replay](recover_tax.py)
