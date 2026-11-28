# Whole-Actor search round 2

**Keep Scope as the shared incumbent. Neither new prompt advances to the 40-task comparison.** Two matched whole-prompt refinement rounds find no protected primary gain on an additional task once the pre-existing no-history birthday case is isolated. The second paired prompt is closer to Scope than its first revision but its stronger overall score versus the ordinary optimizer does not identify better application of history.

| JCC evidence, 12 jointly valid development tasks | Specialist archives | Scope | Handwritten seed | Ordinary search R2 | Paired criteria search R2 |
|---|---:|---:|---:|---:|---:|
| Internal equal-domain score | 70.79% | 79.54% | 70.34% | 69.20% | 78.39% |
| RPEval Match | 11/29 | 17/29 | 9/29 | 8/29 | 16/29 |
| RPEval OPB / UPB / FM | 8 / 4 / 1 | 4 / 3 / 4 | 6 / 7 / 4 | 5 / 9 / 4 | 5 / 4 / 4 |
| BenchPreS AAR | 4/5 | 2/5 | 2/5 | 2/5 | 2/5 |
| BenchPreS non-bold AAR | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 |
| BenchPreS MR | 1/15 | 0/15 | 0/15 | 0/15 | 0/15 |
| BenchPreS completeness sum | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| PersistBench passes | 3/4 | 4/4 | 4/4 | 4/4 | 4/4 |

Under the ordinary-gate evidence condition, the same columns give 70.79%, 78.47%, 68.12%, 68.12% and 78.47%. The paired round-two prompt ties Scope's Match there (18/29). The JCC condition remains primary. In pairwise RPEval excluding known flags, paired round two and Scope tie at 10/22 on three cases. Score validity filters do not detect all attribution problems.

## What changed in the answers

- The new paired benefits-update answer explicitly records the actual marital and retirement states. Completeness recovers from 3 in round one to 5, matching the incumbent. This is improved task implementation from refinement, with no gain over Scope.
- The birthday case receives no history in either input mode. With JCC evidence, its score is 0/7 for Scope and ordinary round two, 7/7 for paired round two. It accounts for seven of the eight matched-position difference between the second ordinary and paired branches. The other tasks are 17/22 Scope, 8/22 ordinary and 9/22 paired. This is a sensitivity check; the original benchmark scores remain unchanged.
- In the family coastal itinerary, the paired round-two answer scores 3/8 on JCC evidence, as did Scope and both round-one revisions. This input still lacks the earlier aversion source. The new prioritization language cannot restore an unseen constraint.

The best-of-saved-answer oracle over both rounds could add seven protected primary positions in RPEval; all seven come from the no-history birthday case. Outside that case, no saved rewrite can add even one primary position without worsening the fixed protections across the tested tasks. BenchPreS and PersistBench have no primary gain in that oracle inventory. This result is limited to the sampled completed answers and the 12-task exposed fit panel. It does not exclude other search methods or better models.

## Execution and decision

Both optimizers read the same six fit-group record sets. Their answer excerpts were capped at 700 characters for both proposals to fit the fixed request budget; the selected original evidence and current task were retained in full in the feedback packets. Online Actors received only the original task, facts, plan, and source set. The proposal contracts differ in feedback packaging and guidance; this is neither an exact author GEPA reproduction nor a proof of an advantage from paired feedback.

All **130 physical requests** succeeded: 2 proposals, 34 unique Actors, 10 RPEval judges, 72 BenchPreS judges and 12 PersistBench judges, with **468,936 reported tokens** and no unknown usage. The earlier seed was read from the archive. Across both rounds, **306 physical requests** succeeded with **1,158,815 reported tokens**, excluding inherited calls. No sealed input was touched, and no prior score was rewritten.

The next performance hypothesis must change more than the instruction phrasing or the organization of feedback, or establish that the bottleneck is the model under the frozen contract. Preserve the three benchmarks, and keep original rubric results alongside the no-history attribution controls. Neither a best-of-saved oracle that knows the grades nor optimizations of zero-exposure score artifacts is a deployable candidate.

[Protocol](FIRST_PASS_SEARCH_PROTOCOL.md) · [Full reviewed prompts](FIRST_PASS_ROUND2_PROMPTS.json) · [Aggregate results](FIRST_PASS_ROUND2.json) · [Both-round frontier](FIRST_PASS_FRONTIER.json) · [No-history attribution control](NO_HISTORY_RPE_GRADES.md)
