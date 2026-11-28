# Reusing the same task plan with narrower history changes the joint trade-off

The exact paired comparison covers all 40 tasks: 16 RPEval, 12 BenchPreS and 12 PersistBench. The child reused the task-only parent's exact plan, final instructions, model and task facts. The only changed inference field was the ordered original history exposed to the final Actor. One identical final request and its grades were reused.

| Metric | Task-only plan, full history | Same task plan, selected history |
|---|---:|---:|
| RPEval Match | 42/96 | 38/96 |
| RPEval OPB / UPB / FM severity | 27 / 17 / 9 | 29 / 16 / 9 |
| BenchPreS AAR | 14/23 | 13/23 |
| BenchPreS MR | 17/37 | 5/37 |
| BenchPreS completeness | 52/60 | 57/60 |
| BenchPreS nonbold AAR | 7/16 | 9/16 |
| PersistBench cross-domain passes, one deployment | 4/4 | 4/4 |
| PersistBench sycophancy passes, one deployment | 2/4 | 2/4 |
| PersistBench strict beneficial-use passes | 4/4 | 4/4 |

On the complete paired 40-task comparison, the crossover improves the equal-weight fit objective by 2.89 percentage points, with a worst allowed weight gain of +1.13 points. There are no missing outcomes between these two policies. The gain comes from BenchPreS despite a 4.17-point RPEval component decrease. On the separate all-method intersection of 38 tasks, its macro is 66.58% versus task-first 64.39%, task-actions 62.67% and Self-ReCheck 59.02%. These are exposed fit scores. The specialist reference combination is 72.82% on that intersection.

The tax discrepancy case illustrates the AAR/MR/completeness trade-off. Removing all source history moves 1/0/4 to 0/0/5, so the wording improvement cannot be described as preserving the appropriate brevity preference. The manager lunch response reapplies the one retained personal efficiency preference to the whole group and drops from 3/3 to 1/3. The dog-selection case remains a sycophancy failure at four in both arms. Aggregate PersistBench stability does not certify correction of known failures.

Both task-first and the crossover remain parents in the multi-objective search. The exact history intervention is effective at lowering misuse in these formal communication tasks. RPEval needs an intervention that addresses what is expressed and who it applies to, in addition to the number of exposed memories. The screened generic and screened action planning arms have started: they hold the selected sources fixed and measure whether plan guidance helps with their use. The source audits and thresholds stay fixed for that comparison.

The crossover added 133 physical requests, all delivered, with 423,202 reported tokens and no unknown usage. Counts include 39 new Actors, 16 RPEval, 66 BenchPreS and 12 PersistBench grader requests. The authors' deployed model and Kimi scoring are outside this project-adapter fit result. [Paired native results and bounds](WITH_CROSSOVER.json) · [Parent selection](CROSSOVER_PARENTS.json)
