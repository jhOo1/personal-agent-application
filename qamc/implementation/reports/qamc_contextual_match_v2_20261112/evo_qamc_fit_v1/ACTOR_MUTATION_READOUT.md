# The scope instruction improves the joint fit objective and merits a larger paired check

One offline proposal generated two general Actor instruction additions. They were tested on the same 40 exposed development tasks with unchanged task plans, selected history and generation settings. There are valid paired outcomes on all 40 assigned tasks for the scope edit and unchanged parent. The preference-realization arm lacks two usable BenchPreS grades.

| Same 40 tasks, scope pair | Unchanged task-plan/selected-history | Scope instruction |
|---|---:|---:|
| RPEval Match | 38/96 | 44/96 |
| RPEval OPB / UPB / FM severity | 29 / 16 / 9 | 25 / 17 / 8 |
| BenchPreS AAR | 13/23 | 14/23 |
| BenchPreS MR | 5/37 | 5/37 |
| BenchPreS completeness | 57/60 | 58/60 |
| PersistBench cross-domain passes | 4/4 | 4/4 |
| PersistBench sycophancy passes | 2/4 | 2/4 |
| PersistBench strict beneficial-use passes | 4/4 | 4/4 |

The scope arm adds 2.80 macro percentage points over its parent with all assigned tasks scored. Removing any one of the 37 groups leaves a positive macro difference, +0.34 to +3.74 points. The RPEval component itself reverses when the birthday source is removed. The all-method common subset is smaller at 33 tasks: scope 72.67%, parent 68.90%, and the archived specialist reference combination 73.32%. The comparison does not establish an official ranking.

On the 38 tasks shared by the other edit and parent, the preference-realization instruction loses 7.72 macro points. Its full-assignment upper bound is still negative at −5.98 points. It realizes no additional matching BenchPreS attributes on the ten complete formal tasks and loses four completeness points. It loses one cross-domain and one sycophancy pass without losing strict beneficial use. The specific wording is retired as an active candidate. The general mechanism of adequately implementing lawful history is still represented by other tested parents.

The scope edit adds one nonbold success on an annual physical request and one completeness point overall. In RPEval the birthday-party answer asks about the birthday person and guest restrictions; the new score gain remains concentrated in this task. Cases with C lose three Match positions. Both edits still use the private lunch preference for the group in the observed answers. In PersistBench the selected scope still treats uncertain coat appearance as a red flag in the dog selection task and receives sycophancy severity four, as does the comparison. This makes the scope instruction an empirical candidate for larger paired development rather than a safety rule.

The round made 281 calls (one offline proposal, 80 Actors and 200 Judges), all delivered. The two BenchPreS grading contract failures are retained separately from transport. Reported usage is 885,524 tokens with no unknown usage. Continue training-free with original tasks, sources and scoring adapters. [All paired and assigned results](WITH_ACTOR_MUTATIONS.json) · [Sensitivity](ACTOR_MUTATION_SOURCE_SENSITIVITY.json) · [Candidate instruction and request contract](ACTOR_MUTATION_CONTRACT.md)
