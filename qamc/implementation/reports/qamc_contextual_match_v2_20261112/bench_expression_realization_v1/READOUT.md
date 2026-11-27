# Specialist simplification did not recover BenchPreS brevity

**Keep Strong Gate. The current expression realization variant does not advance.** The frozen TS-T5 specialist and a Qwen sentence editor processed the same candidate sentences and passed through the same literal and two-way NLI tests. Only the archived answer could be modified. No fresh full-answer Actor was called.

| Same 8 exposed tasks | Strong Gate | Qwen local edits | TS-T5 local edits |
| --- | ---: | ---: | ---: |
| All appropriate attributes, AAR | 11/15 | 11/15 | 11/15 |
| Inappropriate attributes, MR | 0/25 | 0/25 | 0/25 |
| Average task completeness | 4.625 | 4.625 | 4.625 |
| Target brevity attribute | 2/6 | 2/6 | 2/6 |
| On the four frozen misses | 0/4 | 0/4 | 0/4 |

All eight tasks have common valid scores from the project Qwen adaptation. The four misses are different tasks from the same profile. The two previously followed brevity tasks span both represented brevity profiles. The two other profiles are abstention controls and were unchanged. These are exposed development results with zero independent human reviews. This experiment uses the authors' TS-T5 release instead of MUSS. It measures transfer to professional messages and does not evaluate MUSS.

## What actually changed

The frozen design identified 11 sentence spans on four tasks, seven on misses and four on fulfilled cases. Both generators had one candidate opportunity per span. The program preserves original text outside an accepted span and restores original bold wording when present. In both methods the only candidate that passed the literal rules also passed the 0.75 two-way entailment cutoff. This means the small realized edit count was mostly limited before NLI, not by NLI rejecting several otherwise admissible rewrites.

- Qwen proposed five insufficient shortenings, four changes that could not restore protected emphasis or formatting, one null, and one admissible edit. The admitted edit on the rental-history task changed “any additional” to “more.” That removed one word and did not recover the target attribute.
- TS-T5 proposed five insufficient shortenings, five changes that could not restore protected emphasis or formatting, and one admissible edit. Its only admitted edit was on an already fulfilled task. It removed one word and rewrote “am prepared to” to “will.” That increases commitment strength. The literal checks and two-way NLI both accepted it, and the unchanged native scores did not surface it. This is a concrete protection failure; unchanged score fields do not certify unchanged meaning.
- A lower threshold alone would not be a justified fix. Format rejections protect already-emphasized content, and relaxing them would require a fresh experiment with explicit protection. The monitored all-task effect is zero under the fixed protocol, and the original answers remain the deployable reference.

## Calls and recovery

Local inference generated 11 specialist proposals and evaluated four NLI directions, using pinned model, tokenizer, config and software hashes. The treatment does not update either model. The shared compiler's sentence-format contract passed five offline tests. There were **16 new physical requests**: four ordinary sentence-edit jobs and twelve native-adaptation score jobs for the two changed answers. All requests succeeded, **19,860 reported tokens**, zero unknown usage and no reissues. Unchanged outputs use the corresponding verified Strong Gate grade. The zero-cloud replay reproduced all local proposals, the final results and the ledger. No sealed data were opened. Model weights and private request and result records remain outside the public archive.

[Protocol and citations](PROTOCOL.md) · [Frozen configuration](FROZEN_PUBLIC.json) · [Matched aggregate](SUMMARY.json)
