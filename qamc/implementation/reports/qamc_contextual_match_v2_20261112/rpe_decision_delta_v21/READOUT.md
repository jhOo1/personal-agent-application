# RPEval single-call decision edit result

The primary DELTA arm gets one more Match than the same-input FREE editor and the retained V1 draft on 21 common positions. The advantage over FREE survives the two missing-score completions on the frozen 22-task historical panel. There is no robust net gain over V1 after accounting for the unresolved DELTA score, and some severity measures worsen. Separately removing the leading list markers from rejected proposals exposes actual regressions and erases the primary net advantage. Do not promote the current method or the presentation projection as a replacement for V1.

| Historical overlap, same 21 valid tasks | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| RP reconstruction | 16/21 | 0 | 7 | 14 |
| Des2Gen adaptation | 17/21 | 1 | 7 | 21 |
| MemAdapter adaptation | 18/21 | 3 | 3 | 11 |
| IPE-C | 14/21 | 0 | 23 | 27 |
| V1 selected draft | 18/21 | 1 | 2 | 9 |
| FREE | 18/21 | 2 | 1 | 13 |
| DELTA | 19/21 | 2 | 3 | 10 |
| DELTA with presentation projection | 17/21 | 2 | 3 | 14 |

Of the 24 assigned tasks, 22 have the historical reference selection of outcomes. There are 21 common valid scores on those 22 and 22 common valid scores across all 24. On the broad common 22, the relevant totals are V1 19, FREE 19, DELTA 20 and projected DELTA 18. There is one Score JSON contract failure for each arm and no delivery failures. On the selected historical intersection, DELTA versus FREE is two wins, one loss and 18 ties. Relative to V1, FREE has two recoveries and two regressions. DELTA has one recovery and no observed Match regression. The full historical missing-data bounds for primary DELTA minus FREE are [1, 2], and for primary DELTA minus V1 [0, 1]. The missing DELTA restaurant position includes a visible negative match field in a structurally invalid result. Its original missing status is retained.

## Actual output differences

- **Omega-3 food recommendations:** both editors recover the archived Match miss. The DELTA arm retains its original nonseafood recommendations. Its one accepted group adds a repeat of the supplement and conditional seafood suggestions, with an additional qualification. This supports treating the Match flip as ambiguous evidence of improved behavior. Presentation projection adds another duplicate, and the score returns to a miss. The user history describes a pattern of avoiding seafood, and does not establish an absolute or medical exclusion.
- **Parents' brunch:** DELTA places a short request for a creative or seasonal item inside an actual recommendation slot. The edit adds the idea at the correct structural level, but its wording still gives no concrete dish. FREE names specific creative options that coexist with familiar choices for the parents. FREE recovers this B position and DELTA remains a miss. A syntactically local option edit can still be semantically underspecified.
- **Winter formalwear and cold-weather family packing:** V1 and DELTA retain the two passing Match outcomes. FREE pushes the former toward general formalwear, and reintroduces unrelated camping history in the latter. The DELTA packing treatment preserves V1 after a group rejection. When that group is recovered by dropping its leading marker, the outdoor-history insertion reappears and the job is regraded as a miss.
- **Pet travel on the full roster:** the original passing V1 draft remains intact under the DELTA group contract. The projected edit adds irrelevant table-setting preference to the packing list and becomes a miss. FREE's score is structurally invalid on this item, so it is excluded from the common table. The visible FREE reason also objects to a similar insertion, which remains a diagnostic only.

## Disposition, sensitivity and costs

FREE rewrote 23 of 24 drafts. The bounded treatment changed 11, including one partial edit with one group retained and another group rejected. It explicitly kept three and fell back on ten. Twelve groups passed in the main trial, including nine OFFER, two QUALIFY and one TRIM. An accepted group shows that its text and inputs satisfied the contract. The check cannot prove that the group serves the current party, is specific enough, or changes recommendation quality.

The separately frozen presentation sensitivity uses the same sampled proposals and only removes one leading bullet or ordinal from an otherwise single-line action. Nine final answers change. Three previously passing bounded edits or baseline fallback answers become misses in the full roster and no new Match recovery appears. Two of these losses are on the common 21. This is evidence that the current planner proposes some harmful or redundant content. It does not establish that a Markdown marker is a reliable semantic filter.

The main study made 48 real generation and 34 scoring requests, all transport-successful, with 503,587 tokens reported. The projection uses 9 more scoring requests, all delivered, with 25,727 tokens. Combined, 91 requests and 529,314 reported tokens, with no retries, no usage missing and no new sealed access. Two structurally invalid scores are preserved. All evaluations use the same adapted Qwen RPEval protocol.

Keep V1 for the current benchmark comparison. The next useful experiment should target a verified semantic trace: willingness to act on a preference only when the action serves the present task, preserves the necessary recipient conditions and offers a concrete new option. Measure both recoveries and ordinary regressions against V1 and the equal-budget editor. Reduce duplicated proposals before editing and avoid making score-driven, task-specific choices. The main net Match finding on 21 tasks remains development evidence.

[Main aggregates](SUMMARY.json) · [Main execution audit](AUDIT.json) · [Presentation method](PRESENTATION.md) · [Projection aggregate](PRESENTATION_SUMMARY.json) · [Projection cost](PRESENTATION_COST.json)
