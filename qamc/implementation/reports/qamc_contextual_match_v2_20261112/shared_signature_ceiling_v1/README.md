# Can an observable signature choose one protected action across benchmarks?

Retrospective integer optimization of the previously frozen paired-regret matrix. Each distinct signature gets exactly one of the same three archived action paths T/H/G (task-only, full RP, Strong Gate). Scores are read to construct an optimistic ceiling. No score-derived mapping is exported. Reuses every benchmark-specific aggregate protection from the original matrix, including the sign conventions for severity, misuse, completeness and strict helpful use. Benchmark identity enters constraints and reporting but never the shared signature. Complete-score intersections: 228 RPEval (1219 positions), 26 BenchPreS (44 applicable attributes), 42 PersistBench (42 outcomes). Different adapted grading protocols. Fitting and evaluation here use the same exposed records.

|Information in the signature|RPEval Match|BenchPreS AAR|PersistBench passes|
|---|---:|---:|---:|
|Frozen strong reference|814|38|38|
|All rank summaries, specialize the post-hoc rule by domain|885|38|41|
|All rank summaries, one shared post-hoc rule|875|38|41|

All three shown shared maxima are simultaneously attainable while matching or exceeding every reference protection in aggregate. The original one-bit IPE trigger, even allowing arbitrary reassignment of T/H/G to its two states, admits no joint protected solution. It is already infeasible on PersistBench by itself; BenchPreS and RPEval also have no jointly feasible one-bit assignment even without PersistBench. Under full rank summaries the RPEval/PersistBench optima coexist. Adding BenchPreS reduces the maximum RPEval gain by ten positions. This shows a localized trade-off for these specific action paths and representations.

The full features are twelve pre-generation aggregate values derived from the existing estimator ranks, including candidate count. There are 238 distinct signatures on 296 rows, only five shared across benchmarks; a retrospective table can largely memorize observations, especially on PersistBench (42/42 distinct). This is feasibility on existing records, not a deployed policy, an independent result or a proof that raw task inputs conflict. Aggregate protections allow compensating gains and losses across tasks. No new requests or sealed data. The earlier source-separated low-capacity fit failed its protections. Retain all three benchmarks, do not deploy this lookup, and do not infer a need to discard a benchmark from a one-bit failure.

Run compare.py using the private restored paired_regret_policy_v1 matrix and SciPy. Every optimal solution is checked after integer rounding against its original inequalities; no timeout or indeterminate solver result counts as infeasible.
