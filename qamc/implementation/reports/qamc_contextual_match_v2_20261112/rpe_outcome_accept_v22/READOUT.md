# Outcome acceptance on fixed RPEval revisions

**Keep V1.** The structured effect reviewer does not improve over the matched standard reviewer on these archived answers. Both preserve the same Match outcomes in their common comparisons. An observed useful review decision does exist: both reject a repeated dietary recommendation with a disputed positive adapted Match change. The effect reviewer did not uniquely accomplish that rejection.

| Same 21 scored historical tasks | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| RP reconstruction | 16/21 | 0 | 7 | 14 |
| Des2Gen adaptation | 17/21 | 1 | 7 | 21 |
| MemAdapter adaptation | 18/21 | 3 | 3 | 11 |
| V1 selected draft | 18/21 | 1 | 2 | 9 |
| FREE delivered without review | 18/21 | 2 | 1 | 13 |
| DELTA delivered without review | 19/21 | 2 | 3 | 10 |
| FREE with either review | 18/21 | 2 | 1 | 13 |
| DELTA with either review | 18/21 | 2 | 3 | 10 |

The controls share the same V1 draft, completed candidate, order, raw history and task text. Both FREE reviewers adopt all 23 changed answers. The general DELTA reviewer adopts 8 of 11 changed answers and the effect reviewer adopts 9. They differ on one Italian travel food draft. Both options have the same available Match and reported OPB, UPB and FM. No scoring request was repeated or added to resolve invalid grades.

In the full historical 22-task FREE allocation both reviewers finish at 18/22 against V1 at 19/22. They accept two observed recoveries, three regressions and 16 unchanged Match positions. The DELTA arms' effect-minus-generic bound is [−1, 1] and their delta bound versus V1 is [−1, 0]. Each selected the same unscorable prior DELTA answer on the missing historical position. Keep the unknowns as recorded and compare the exact 21-task intersection.

## Actual acceptance behavior

- **Omega-3 recommendations:** both DELTA reviewers identify the same practical problem with adopting the edit. It repeats the supplement and fish guidance. Original benchmark adaptation nevertheless assigned the edit a positive Match. Rejecting it is a defensible behavior choice and costs one reported Match. Neither acceptance reviewer uniquely detects this issue.
- **Family winter trip:** both FREE reviewers accept the version that invokes unrelated camping history and adds extra outdoor packing suggestions. The effect reviewer explicitly credits the history-linked additions. Normal warmth and traction advice would already be justified by the trip, but the added optimization target is unsupported. The effect prompt does not isolate that distinction here.
- **Winter formalwear and Rome restaurants:** both FREE reviewers favor the broader revised recommendation. Both revisions lose adapted Match. For formalwear the stated reason prefers greater variety and discounts the original preference priority. For the restaurants, real availability and exact eligibility remain unverified. This is a comparison of decisions on fixed evidence, not verification of vendors.
- **Brunch with parents:** both FREE reviewers accept the contentful addition of compatible specific options. This confirms they can recognize at least some optional benefits. No distinct recovery from the effect instructions is observed.

Cap and actual cost are 68 physical Qwen reviewer calls across the 34 changed drafts. All 68 delivered and had usable JSON. Observed usage is 187,071 tokens, with zero unknown usage, retries, Actor calls or new scoring requests. The two invalid original grade records remain unchanged. No sealed cases were used. This comparison is restricted to one frozen RPEval development inventory.

Use these observations to avoid equating a generic post-hoc filter or additional editing with validated efficacy. On the broader development inventory, test generation that makes an actual alternative decision conditional on appropriate evidence, with no unsupported current relationship and no forced change to the participant's requirements. Keep same-candidate comparisons and check whether a new proposal is actually absent from the base answer.

[Summary and paired bounds](SUMMARY.json) · [Protocol](PROTOCOL.md) · [Runner](acceptance.py)
