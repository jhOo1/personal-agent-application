# RPEval protected decision repair results

The frozen API-only comparison is settled. Scope-limited repair produced a useful new answer for the plant-protein task and preserved more of the draft on that item. The equally informed free revision also fixed it. The two methods had the same result on every common valid item, so this trial does not establish a Match advantage for the bounded executor.

| Historical overlap, same 13 valid items | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| RP reconstruction | 9/13 | 0 | 2 | 8 |
| Des2Gen adaptation | 10/13 | 0 | 2 | 9 |
| MemAdapter adaptation | 10/13 | 2 | 3 | 9 |
| IPE-C | 8/13 | 0 | 13 | 16 |
| V1 witnessed whole-answer choice | 10/13 | 0 | 2 | 7 |
| FREE | 10/13 | 0 | 2 | 6 |
| PATCH | 10/13 | 0 | 2 | 6 |

All 24 tasks were assigned. The reference overlap has 22 tasks, and FREE and PATCH have 13 and 14 valid scores on it. The 15 common valid tasks on the full roster yield RP 11/15 and Des2Gen, V1, FREE and PATCH each 12/15. PATCH versus FREE is 0 wins, 0 losses and 13 ties on the primary common subset. Both revised arms are 1/2 on A, 4/5 on B and 5/6 on C. Accounting for every unknown score as either 0 or 1 leaves the primary Match delta at [−6, 2] against RP, [−8, 9] against FREE and [−8, 0] against V1. These are missing-data bounds, without assigning any unknown an observed outcome.

## What actually changed

- **Plant-protein muscle gain:** the original already supplied plant-protein choices. PATCH deleted a single additional recommendation that contained animal products and preserved the entire rest of the draft. FREE rewrote the answer and also removed animal-product recommendations. Both moved the archived adapted Match from 0 to 1. PATCH retains 263 of 296 original characters and delivers 263. FREE has 183 aligned characters and delivers 1,016. The length difference is observable without asserting that shorter is universally better.
- **Seafood on the Japan trip:** the locator correctly identified a positive seafood suggestion and supplied a valid witness and an exact target, alongside an undeclared replacement field. The frozen trial discarded that locator response and both arms retained RP. The original RP Match is already correct. Any later advantage needs to be described in terms of actual recommendations, supported taste preferences and appropriately qualified ingredients.
- **Brunch for parents:** the locator observed that the original prioritized mild flavors and overlooked the requester's openness to novelty. Its exact scope also failed the envelope check. Both arms retained the original miss. Whether a creative alternative is appropriate for the group must be judged from the revised answer, including any conditions attached to that option.
- **Children's vegetable dishes and omega-3:** the valid locator returned KEEP on both and neither arm could repair the remaining RP miss. The first needs a check on whether the draft introduced an unnecessary group-level nutrition objective, without treating protein-containing dishes as intrinsically invalid. The second requires distinguishing a historical seafood habit from a firm restriction. Winter formalwear had an unknown locator delivery and provides no V2 execution evidence.
- **Other edits:** PATCH removed a fruit-associated fragrance suggestion, added a recipient preference check in a party plan, and revised a linked workout playlist and its order. An unrelated safety qualification in the cold-weather packing list also preserved Match. The four rows with valid edited answers on both arms had median aligned drafted text of 95.5% for FREE and 95.9% for PATCH. This is a descriptive character alignment. The guarantee of unchanged bytes outside chosen targets comes from the executor.

## Execution, failures and decision

There were 43 physical requests. Locator 24, revision 10, scoring 9. The locator returned 5 valid ACT plans, 7 KEEP, 4 envelope rejections and 8 delivery-unknown responses. One FREE revision had unknown delivery. Nine changed answers were truly new, and all nine scoring requests returned complete usable scores. The other valid outputs reused exact original grades. Reported usage is 201,544 tokens with 9 unknown records and zero retries. No prior answer, failure or score was overwritten.

Do not advance this frozen executor to a larger benchmark panel on this result. There is only one observed recovery, shared with FREE. Structural checks remain useful for limiting changes, and the unresolved weaknesses are separated. Recoverable formatting losses are investigated in the separately frozen [locator sensitivity](LOCATOR_RECOVERY.md). Actual KEEP on observed misses requires a better decision rule, and unknown deliveries require complete receipts on later authorized experiments. The inherited evaluator is the project's detailed Qwen RPEval adaptation on exposed development tasks.

[Aggregates](SUMMARY.json) · [Execution and missing-data audit](AUDIT.json) · [Frozen protocol](PROTOCOL.md) · [Recovery](RECOVERY.md) · [Related mechanisms](RELATED_MECHANISMS.md)
