# Paired effects and sensitivity to source groups

Use 10,000 fixed-seed source-group resamples. Keep both methods and all same-task preference or attribute scores together when sampling a group. Differences use the pooled endpoint numerators and denominators within a draw. Resampling intervals describe stability conditional on each exposed panel and its project grader. They do not estimate independent confirmation error, and a degenerate interval for observed ties does not establish noninferiority. Leave-one-group-out ranges show the smallest and largest effects after removing any one participating group.

| Paired development effect | Common valid support | Candidate − control | Resampling 95% interval | Leave-one-group range |
|---|---|---:|---:|---:|
| RPEval IPE-C vs RP, overall Match | 274 tasks, 1,462 positions, 44 groups | +8.82 pp | [3.09, 14.86] | [6.70, 9.85] |
| RPEval IPE-C vs task-only, overall Match | Same | +5.40 pp | [2.37, 8.34] | [4.53, 6.10] |
| RPEval IPE-C vs RP, all-A Match | 512 positions, 43 groups | +25.98 pp | [12.50, 38.99] | [20.85, 27.47] |
| RPEval IPE-C vs RP, only-B Match | 278 positions, 19 groups | −0.72 pp | [−12.75, 10.53] | [−4.17, 3.82] |
| BenchPreS Strong Gate vs Selectivity, MR | 126 attributes, 10 profiles | −8.73 pp | [−12.00, −4.39] | [−10.00, −7.55] |
| BenchPreS Strong Gate vs Selectivity, non-bold AAR | 43 attributes, 7 profiles | −2.33 pp | [−9.62, 6.06] | [−5.41, 0.00] |
| PersistBench SELECTED_GEPA vs PB_RUBRIC, strict pass | 49 tasks and groups | +8.16 pp | [0.00, 18.37] | [6.25, 10.42] |
| PersistBench SELECTED_GEPA vs Full MemAdapter, strict pass | 48 tasks and groups | +18.75 pp | [8.33, 31.25] | [17.02, 19.15] |

The overall RPEval and PersistBench advantages survive the removal of any one recorded source group. Against RP, both RPEval all-A improvements and the less reliable B-only results must be reported. On only-B the sign changes as individual groups are omitted. The small negative result on C-bearing tasks is concentrated in one remaining OFF case: among three valid C-bearing tasks routed task-only, two tie RP and one loses two positions. RPEval development gains therefore do not establish stronger application of already visible legitimate memory. BenchPreS supports a misuse reduction against the published Selectivity adaptation; the AAR change depends on which attributes are included. PersistBench's interval against the strongest PB_RUBRIC control touches zero despite a positive leave-one-group range. A strong leaderboard claim would require evidence beyond this development resampling.

No new calls or data splits were created. The existing matched aggregate outputs replay identically after exposing their checked score loaders to the script. Group names and per-item values are not included in the public result. [Reproducible script](stability.py) · [All estimates](RESULTS.json)
