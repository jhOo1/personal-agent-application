# Single-preference limits of task-level history activation

On the 24 already-exposed RPEval single-preference tasks, IPE-C improves over its own task-only endpoint on the common set and trails each archived external method. This is a small development panel with four author A, nine B and eleven C. The comparator generation methods are distinct. Old and new grades use the same verified historical detailed Qwen single-preference scoring adaptation.

| IPE-C vs comparison | Common tasks | IPE-C / comparison Match | Win / loss / tie | IPE-C / comparison UPB |
|---|---:|---:|---:|---:|
| Always-Task | 21 | 14 / 10 | 4 / 0 / 17 | 23 / 48 |
| RP / Always-Memory | 22 | 15 / 17 | 0 / 2 / 20 | 23 / 7 |
| Des2Gen | 22 | 15 / 18 | 1 / 4 / 17 | 23 / 7 |
| MemAdapter | 22 | 15 / 18 | 1 / 4 / 17 | 23 / 3 |

IPE-C takes the task-only branch on all 12 implicit tasks and six of 12 explicit tasks. On valid IPE-C answers, it matches 6/11 implicit and 9/11 explicit. This split is descriptive. Format and case identity are not independently varied in this single-preference panel.

## Exact source exposure and verified cases

The archived IPE top rank is B for seven of nine author-B tasks, and A for the other two. IPE-C withholds history for all nine. The adapted grader still assigns 8/9 Match to these nine task-only answers. This does not show that the model used memory that was absent. RP and Des2Gen also score 8/9; MemAdapter scores 9/9.

Of eleven author-C tasks, six are predicted C and receive the history endpoint. Five are predicted B and take the task-only branch. These include both observed losses to RP:

- For the Japanese food request, task-only leads with sashimi and other seafood. The old RP endpoint gives non-seafood options informed by the visible restriction. The task-only answer omits the historical requirement.
- For workout music, task-only includes generic strong-beat options. The old RP answer favors melodic, less repetitive options. The old RP score is higher, while the precise degree of preference authority in the answer remains subject to the adapted Judge.

The controlled issue is which whole Actor input became visible under the same route. The rule always hides an IPE-B source on a single-preference task. On multi-preference tasks, another IPE-C prediction may carry that B source into the full-history request. A zero-call join verifies the route on 295/300 existing multi tasks. Of 138 author-B positions that IPE also predicts B, 68 occur on task-only requests and 70 occur with history triggered by a separate predicted C. In the latter 70 positions, the actual fused RP instruction is B for 67, A for two and C for one. Thus physical exposure, IPE's prediction and the final Actor's use instruction are distinct. No individual position outcome follows from these counts. [Multi-preference coupling counts](MULTI_COUPLING.json). The historical activation rule controls are in the research repository at `rp_estimator_routing_replay_v1/READOUT.md` under the same report parent.

## Protocol and execution

All 72 external-system grades were re-parsed from stored raw responses and matched to their exact expected detailed judging envelopes. The release entry point imports a short template that omits Boolean Match. The retained project adaptation uses the separate detailed author-supplied template and Qwen3.8-Flash. These results do not establish the author leaderboard ranking or official-model parity. [Pinned entry point](https://github.com/XueyangFeng/RPEval/blob/0f8bce80a03e6b86426485264b14ae7de49cc8f9/generation_task/eval_single.py) · [Pinned short prompt](https://github.com/XueyangFeng/RPEval/blob/0f8bce80a03e6b86426485264b14ae7de49cc8f9/prompts_715.py) · [Pinned detailed prompt](https://github.com/XueyangFeng/RPEval/blob/0f8bce80a03e6b86426485264b14ae7de49cc8f9/prompts/prompts_715.py)

One exact task-only Actor was reused. There were 23 new task-only Actor calls and 23 scoring calls. One Actor had unknown delivery and usage after a missing terminal event. Two returned judging responses failed the strict grading contract. Nothing was resent. There are 21 valid task-only outcomes and 22 valid IPE-C outcomes because one unavailable task-only grade is on a routed-history task. All 24 allocations remain in the private run. Total observed cost was 75,554 tokens across 46 requests. No new RP, Des2Gen or MemAdapter calls. No sealed records. [Frozen protocol](PROTOCOL.md) · [Complete denominators, by label and format](SUMMARY.json)
