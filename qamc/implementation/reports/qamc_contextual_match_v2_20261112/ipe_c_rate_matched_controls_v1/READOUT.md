# IPE-C beats equal-rate memory suppression on archived endpoints

Both original endpoints were available for 216 exposed RPEval tasks. IPE-C kept full history on exactly 100. Its original score is 765/1142, compared with 696/1142 for Always-Task and 645/1142 for Always-Memory. When randomly keeping exactly 100 histories, mean Match is 672.3. The result persists when the random policy preserves the original rate in each track and history-size stratum, and when it preserves the exact rate for each identical no-history request.

| Assignment of saved full-history endpoint | Mean or actual Match /1142 | Central 95% reference interval |
| --- | ---: | ---: |
| IPE-C actual | 765 | — |
| Always-Task actual | 696 | — |
| Always-Memory actual | 645 | — |
| Same 100 history-enabled tasks in expectation | 672.3 | 639–705 |
| Same full-branch count per track and history size | 700.2 | 671–729 |
| Same full-branch count per identical public task | 674.9 | 648–702 |

The exact-public-task comparison allows shuffling only among different histories for exactly the same task-only request. It has 34 mixed blocks among 47 and 177 movable tasks, 941 positions. On those 177 tasks, IPE-C scores 653/941 versus a shuffled mean of 562.9/941. The matched controls therefore support a distinct history-sensitive routing effect in this exposed pool, beyond the amount of history used. The expected exact-task shuffled UPB and FM on the movable tasks are 200.6 and 92.9, versus IPE-C 110 and 32. OPB goes the other way, 175.1 versus IPE-C 180. This is a protection tradeoff, and the study does not establish conditional causal performance on other datasets.

Against Always-Task, IPE-C has lower Match on all-A (343 vs 369/432), nearly the same on only-B (100 vs 97/181), and much higher on contains-C (322 vs 230/529). The algorithm's net lift does not require framing all-A as strictly better than no history. Overall OPB/UPB/FM are 206/168/42 for IPE-C and 65/396/206 for Always-Task. Against Always-Memory the same quantity is 314/156/45. Grader fields are severity totals. In particular, unexpected positive UPB can occur even for all-A. Three permutation families use 10,000 draws each; the bands describe simulated references, not confidence or independent-test p-values. All cached answers and scores retained, new calls zero.

Per-stratum results and all simulated distributions remain in the original worktree under the corresponding experiment directory. [Recovery access and evidence](../../../../EVIDENCE_INDEX.md) · [Protocol](PROTOCOL.md)
