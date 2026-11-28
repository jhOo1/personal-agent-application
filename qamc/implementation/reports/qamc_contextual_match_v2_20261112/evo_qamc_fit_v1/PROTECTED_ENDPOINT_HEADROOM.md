# How far can the saved exposure routes reach with specialist protections?

The three endpoints are previously run Scope answers with fixed Actor and task plan, seeing no history, selected history or full history. The archived benchmarks' specialist answers remain the comparison: IPE-C, Strong Gate, and PB_RUBRIC. This audit requires all three endpoints and the specialist to have a valid score on the same source; the ordinary Gate score is not required. For this reason its common cohort can differ from the [five-method exposure table](EXPOSURE_FINAL.md).

Use RPEval Match as the objective, and require each of OPB, UPB and FM to be no higher than the specialist on the same task. Use BenchPreS AAR, with MR, completeness and appropriate non-bold application protected. The PersistBench tracks are separate binary outcomes with strict beneficial use rather than a weighted composite. Their covered source groups remain in the original track. No external labels enter an Actor request.

| Exposed panel | Common tasks | Archived specialist | Unconstrained best from saved endpoints | Tasks with no endpoint meeting protections | Extra correct units if allowed a perfect switch from the specialist |
| --- | ---: | ---: | ---: | ---: | ---: |
| RPEval | 123/126 | 391/630 | 375/630 | 45 | 30 on 9 tasks in 7 source groups |
| RPEval, no known flags on any method | 58/126 | 207/332 | 211/332 | 20 | 11 on 4 tasks in 4 source groups |
| BenchPreS | 3/4 | 3/3 | 3/3 | 0 | 0 |
| PersistBench cross-domain | 12/12 | 12/12 | 12/12 | 0 | 0 |
| PersistBench sycophancy | 5/6 | 4/5 | 5/5 | 0 | 1 |
| PersistBench strict beneficial use | 13/14 | 13/13 | 13/13 | 0 | 0 |

The final column gives the specialist answer an explicit zero-loss fallback and then chooses improvements with hindsight. It is a ceiling on this fixed archive, not an implementable selector or a score prediction. RPEval offers 25 of those 30 positions in all-A tasks, zero among the B-only tasks and five in tasks containing C. Without the fallback, 45 RPEval tasks have no admissible endpoint at all. The no-flag sensitivity matters: its unconstrained oracle clears IPE-C by four positions, so the all-row limit cannot be generalized to cases absent scoring disputes.

These results separate the next hypotheses. A better selector among the same three candidate answers alone cannot reach IPE-C in the original complete-case table, even with hindsight. The potentially useful fallback gains are concentrated in avoiding unwanted history effects; for a B-only gain on this cohort, the experiment needs to produce an answer that was not already sampled. The BenchPreS completion cohort spans one profile and is saturated in primary score here. It cannot test improvement across profiles. In PersistBench, the existing candidate opportunity is a single sycophancy source alongside saturated utility and cross-domain tracks, so added generation should be justified by behavioral failures or expanded authorized source coverage rather than attempts to tune another router on these few cases.

The audit is zero-call and read-only with respect to saved grades. It excludes missing metric values, checks aligned denominators, and keeps source texts and raw answers private. Reproduce from the original repository with `bash reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/run.sh exposure-protected-headroom`.
