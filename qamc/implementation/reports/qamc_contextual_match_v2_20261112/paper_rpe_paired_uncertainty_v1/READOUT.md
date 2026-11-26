# RPEval full-task accuracy changes the comparison to empty history

This offline reaggregation uses the archived GPT-4.1 detailed-rubric grades on the frozen 300-task exposed multi-preference panel. It adds the RPEval paper's whole-task metric shape, where every preference position must match, alongside the existing position-level metric. Both remain project-adapted measures. The official short-template incompatibility remains open. [Author metrics, Appendix B.6](https://arxiv.org/html/2601.16621#A2.SS6)

| Method | Micro Match, common 1,462 positions | Whole-task Match, common 274 tasks | Mean overall Judge severity, lower is better |
| --- | ---: | ---: | ---: |
| IPE-C | 953/1,462 | 95/274 | 1.646 |
| Always-Task | 874/1,462 | 103/274 | 1.960 |
| Always-Memory, RP-Reasoner reconstruction | 824/1,462 | 64/274 | 1.942 |

IPE-C improves both Match scopes versus full history, but its advantage over empty history is specific to individual preference positions. The Judge severity sums behind the last column are 451, 537, and 532, respectively. All 822 stored whole-task flags on these common tasks agree with the independently computed all-position indicators. IPE-C's selected answer hash and complete grade match the selected archived endpoint on all 274 rows.

| IPE-C minus comparator | Micro delta, pp | Source-group resampling range, pp | Whole-task delta, pp | Source-group resampling range, pp |
| --- | ---: | ---: | ---: | ---: |
| Always-Task | +5.40 | [2.40, 8.25] | −2.92 | [−6.08, 0.00] |
| Always-Memory | +8.82 | [3.10, 14.84] | +11.31 | [5.44, 17.08] |

The table uses the central 95% of 10,000 paired resamples of the 44 observed source groups. It describes sensitivity within this panel. Groups can remain related and the panel informed development. Across single-group exclusions, the micro gain versus Always-Memory ranges from +6.70 to +9.85 pp. Under extreme missing assignments on all 300 allocated tasks, the corresponding micro difference stays positive [+44, +206] of 1,606 positions, and the whole-task difference is [+17, +48] tasks. Both full-allocation bounds against Always-Task include zero, at [−32, +184] positions and [−28, +10] tasks. Four missing route labels were checked against the pinned author rows solely to count their known positions. No grades were filled.

The 110 common tasks containing at least one author C show the sharpest metric split. IPE-C gains 102 correct positions over empty history (408 vs 306 of 672), yet whole-task Match is 0 vs 3. Both complete-memory answers and the selected IPE-C answers have 0/110 exact on this stratum. Of all 274 common tasks, 163 have no exact draft in either endpoint. A policy that only chooses between those exact archived endpoints cannot make these tasks whole-task successes. This is a diagnostic limit of the archived drafts and scoring, and does not identify which app-level edit would fix them. Excluding any known grading flag preserves the overall direction for both metrics. [Machine-readable strata, bounds, and endpoint opportunity counts](SUMMARY.json)

The paper should report both metric scopes. Keep the relative-to-RP result and qualify the empty-history comparison. Candidate-space expansion and better realization of multiple applicable preferences remain research objectives. This analysis made no generation or scoring calls and read only the pinned exposed multi-preference roster and its archived evaluation output. The input grades are in private research commit `c7bb995cc`; the author-row audit is indexed in the paper comparison status. The public replay code takes the restored research checkout's `ipe_c_two_endpoint_completion_v1/RESULTS.json` as its only argument and resolves the adjacent frozen manifest and source files.
