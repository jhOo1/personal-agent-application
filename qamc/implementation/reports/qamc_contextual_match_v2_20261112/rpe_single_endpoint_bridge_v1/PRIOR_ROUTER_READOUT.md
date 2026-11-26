# How much can rearranging the two fixed answer paths recover?

This secondary development analysis transfers the six rules already defined on the multi-preference roster to the 24 completed single-preference allocations. It checks the original MLE and IPE rank permutations, fused policy in the actual RP Actor request, Actor request digest and identity of each saved IPE-C outcome with its selected endpoint. The rules use only archived model predictions. A separate hindsight calculation takes the larger Boolean Match of the two available endpoints. It uses scores and is a ceiling for choosing exactly one of those saved drafts.

| Existing rule | History enabled /24 | Match /21 | Wins/losses/ties vs IPE-C | OPB / UPB / FM |
|---|---:|---:|---:|---:|
| IPE top C | 6 | 14 | 0 / 0 / 21 | 0 / 23 / 30 |
| Either estimator C with the other B or C | 6 | 14 | 0 / 0 / 21 | 0 / 23 / 30 |
| Previous rule or both estimators B | 17 | 16 | 2 / 0 / 19 | 0 / 8 / 16 |
| Fused C | 3 | 12 | 0 / 2 / 19 | 0 / 38 / 41 |
| MLE top C | 2 | 11 | 0 / 3 / 18 | 0 / 43 / 46 |
| Always use the RP history draft | 24 | 16 | 2 / 0 / 19 | 0 / 7 / 17 |

The 21 tasks have both saved endpoints and every external comparison score. The other three are kept in the allocated and available counts in the aggregate. All six rules score 2/3 on the author-A slice and 8/9 on author-B. Both gains of the shared-B rule are author-C cases. That rule also opens history on seven author-B tasks without any changes in Boolean Match there. These three jointly scored author-A tasks are too few to establish protection after expansion. On the prior 216 common multi-preference tasks, opening history for both-estimator B yielded 647/1,142 versus IPE-C's 765/1,142, with its all-A score falling from 343/432 to 224/432.

**The two-draft Match ceiling is 16/21**, equal to the archived RP draft. Des2Gen and MemAdapter each score **17/21 on exactly this intersection**. The ceiling by author A/B/C is 2/3, 8/9 and 6/9. On the same slices, Des2Gen gets 2/3, 8/9 and 7/9, and MemAdapter 2/3, 9/9 and 6/9. The external gap on this sample therefore requires a different answer path or answer body. It survives even a perfect choice between these particular saved endpoints under the archived adapted grades. This is neither a ceiling on fresh samples nor a claim of generalization across source groups.

There were zero new Actor or Judge calls. The original 24-task report, 46 physical requests and grading contract remain unchanged. No reserve data was accessed. The original six-rule implementation and large comparison remain in the research repository at sibling path `rp_estimator_routing_replay_v1/{replay.py,READOUT.md}`. Recompute in the private research checkout using the same runner dependencies as the single bridge plus that sibling directory on `PYTHONPATH`, then run `python prior_router_replay.py`. [Frozen companion protocol](PROTOCOL.md) · [Single-preference execution report](READOUT.md) · [Replay aggregate](PRIOR_ROUTER_REPLAY.json)
