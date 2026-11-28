# Decisions from a matched development library do not transfer reliably

Same 296 complete development tasks and adapted scorers as the shared-signature ceiling. Three-fold source-separated archive replay, using donor scores only from other folds. These are previously exposed tasks. Ref is IPE-C / Strong Gate / PB_RUBRIC by domain. Primary wins/losses are relative to IPE-C, not the external reference.

|Panel and primary denominator|IPE-C|Exact donors|Nearest donors|Ref|Exact hit / changed|Nearest changed|Nearest wins / losses|
|---|---:|---:|---:|---:|---:|---:|---:|
|RPEval, 228 tasks, Match /1219|814|804|794|814|55 / 4|21|1 / 9|
|BenchPreS, 26 tasks, AAR /44|15|19|20|38|12 / 8|11|5 / 0|
|PersistBench, 42 tasks, passes /42|32|32|33|38|1 / 0|10|4 / 3|

Exact signatures had donors on only 68/296 held-out tasks. Allowing nearest donors for every task raised coverage, but RPEval underuse severity increased from 185 to 202 and FM from 42 to 63, while OPB stayed at 210. BenchPreS completeness fell from 123 to 121 in both transfer variants, MR stayed at one. Full signed-axis counts are in RESULTS.json; negative severity/misuse entries encode costs. A held-out primary win need not preserve the other dimensions. The strict training-donor protection does not prevent held-out regressions. Neither variant should replace the strong references. This tests two prespecified transfer rules, not all possible functions of estimated intent. No weights updated, no model calls, no sealed inputs and no deployment timing claims.

The [retrospective ceiling](../shared_signature_ceiling_v1/README.md) uses the target outcomes to fit its lookup and therefore cannot be presented as a held-out method score. The three original archives contain 300/48/58 assigned rows before estimator and common-score eligibility. The same eligibility filter and fold registry as paired_regret_policy_v1 are used here.
