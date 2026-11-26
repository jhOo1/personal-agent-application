# RPEval with released MemGate on the exact RP Actor

The complete 300-task exposed multi-preference allocation is retained. MemGate and the three fixed comparators use the same RP Actor system, Qwen3.8-Flash generation settings and adapted detailed GPT-4.1 scoring. With the released all-MiniLM encoder and threshold 0.07, only the ordered original Chinese memory arrays and their existing use policies may differ. MemGate inherits the RP strategies corresponding to selected IDs. This is a fixed-retrieval adaptation of the released selector. The benchmark does not start from MemGate's native retrieval or added safety memories.

| Comparator | Shared tasks | Match positions | MemGate / comparator Match | MemGate wins/losses/ties |
|---|---:|---:|---:|---:|
| IPE-C | 276 | 1,477 | 816 / 953 | 14 / 48 / 214 |
| RP with full history | 281 | 1,505 | 832 / 840 | 15 / 25 / 241 |
| Always-Task | 274 | 1,459 | 811 / 869 | 74 / 46 / 154 |

Against IPE-C, the task strata are 252 vs 397 of 512 Match positions on all-A, 163 vs 148 of 282 on B-only, and 401 vs 408 of 683 on C-containing tasks. MemGate increases OPB/UPB/FM severity from 253/257/52 to 370/275/92. Excluding every paired scoring flag leaves 594 vs 691 of 1,001 positions. The observed difference is −9.28 percentage points. Sensitivity to source-group resampling is [−15.04, −3.73] points. Even assigning missing judgments exhaustively in MemGate's favor yields at least 44 fewer matches on the complete allocation. The B-only advantage is one task stratum's aggregate result, not measured accuracy of author-B positions. After excluding grading flags that advantage is 90 vs 89 of 164 positions. [Paired aggregates and missing bounds by stratum](SUMMARY.json)

## Actual behavior

- In an all-A friend-birthday case, six of seven histories remain in the Actor's request. The answer gives outdoor and adventure themes more prominence, reusing considerations in the requester's history. The task-only IPE-C answer gives broader venue and theme options with the friend's interests as conditions. The scores are 0/7 vs 7/7. Several variants share this query and task-only draft, so they cannot be counted as independent demonstrations.
- In the child-outing case, released MemGate excludes the one history record about the child's rejection of crafts. The resulting answer recommends crafts both as an indoor activity and in a rain backup. The adapted Match improves from 3/8 to 5/8 relative to IPE-C despite the visible loss of a relevant activity preference.
- For a query about audio for relaxation before sleep, both history entries reach MemGate's shared RP Actor. The exact reused RP answer does not propose finance audio and scores 2/2. The earlier MemGate answer from a different generator contract did propose finance audio. This makes the case a control against attributing outcomes to visibility alone.

There are 295 verified Actor contracts. The original frozen answers and grades for 136 full- or empty-exposure cases were reused. Two proper-subset Actor receipts and two matching scoring receipts were recovered from authorized development journals. All 157 new Actor and 157 new scoring calls completed transport successfully, with 621,510 reported tokens, zero unknown usage, zero retries. Seven new grades lacked strict valid Match; four endpoint grades lacked it already. Five tasks lacked verified upstream contracts. There are 284 valid MemGate Match outcomes and 16 missing. No old score or sealed data changed.

This experiment supports IPE-C against the frozen released direct-Chinese configuration. It does not identify a general advantage over learning-based filtering in language-matched settings. The paired selector diagnostic documents substantial English-encoder coverage loss and shows that language adaptation changes admission in two distinct ways. [Encoder coverage](ENCODER_COVERAGE.md) · [Language comparison](../rpe_memgate_language_control_v1/WIDE_READOUT.md)
